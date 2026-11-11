"""Testa o POST /encaminhar de ponta a ponta com a API Java de verdade (no Render).

Faz login com a conta de gestor de teste (GESTOR_TESTE_EMAIL e GESTOR_TESTE_SENHA no .env),
e então, conforme as opções:

    python scripts/testar_integracao.py                  # lista os problemas das comunidades do gestor
    python scripts/testar_integracao.py --adotar 12      # adota o problema 12 (muda o banco do grupo!)
    python scripts/testar_integracao.py --problema 12    # chama o /encaminhar/12 do serviço de IA

O serviço de IA precisa estar rodando (uvicorn app.main:app). O token nunca é impresso.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import config  # noqa: E402  (também carrega o .env)

TIMEOUT_LOGIN = 90  # o Render pode levar ~1 min para acordar


def entrar(java: httpx.Client) -> str:
    email, senha = os.getenv("GESTOR_TESTE_EMAIL", ""), os.getenv("GESTOR_TESTE_SENHA", "")
    if not email or not senha:
        sys.exit("Preencha GESTOR_TESTE_EMAIL e GESTOR_TESTE_SENHA no .env.")
    print(f"Fazendo login em {config.java_api_url} (se o Render estiver dormindo, leva ~1 min)…")
    inicio = time.perf_counter()
    try:
        resposta = java.post("/auth/login", json={"email": email, "senha": senha}, timeout=TIMEOUT_LOGIN)
    except httpx.TimeoutException:
        sys.exit("A API Java não respondeu em 90 s. Tente de novo: ela pode ter terminado de acordar.")
    if resposta.status_code != 200:
        sys.exit(f"Login recusado ({resposta.status_code}). Confira o e-mail e a senha no .env.")
    dados = resposta.json()
    if dados.get("usuario", {}).get("perfil") != "GESTOR":
        sys.exit("Essa conta não é de gestor; o /encaminhar só funciona para gestores.")
    print(f"Login ok em {time.perf_counter() - inicio:.1f} s.\n")
    return dados["token"]


def listar(java: httpx.Client, token: str) -> None:
    cab = {"Authorization": f"Bearer {token}"}
    comunidades = java.get("/usuarios/me/comunidades", headers=cab).json()
    gerenciadas = [c for c in comunidades if c.get("souGestor")]
    if not gerenciadas:
        print("Esse gestor não gerencia nenhuma comunidade.")
        return
    for comunidade in gerenciadas:
        print(f"Comunidade {comunidade['id']}: {comunidade['nome']}")
        adotados = java.get(f"/comunidades/{comunidade['id']}/supervisionados", params={"size": 50},
                            headers=cab).json().get("content", [])
        for p in adotados:
            categoria = (p.get("categoria") or {}).get("nome", "sem categoria")
            print(f"  adotado      {p['id']:>5}  {p['titulo']}  ({categoria})")
        feed = java.get(f"/comunidades/{comunidade['id']}/problemas", params={"size": 20}, headers=cab).json()
        for p in [p for p in feed.get("content", []) if not p.get("adotado")][:5]:
            print(f"  não adotado  {p['id']:>5}  {p['titulo']}")
        print()
    print("Para testar: --problema <id de um adotado>. Para adotar um de teste: --adotar <id>.")


def adotar(java: httpx.Client, token: str, problema_id: int) -> None:
    resposta = java.post(f"/problemas/{problema_id}/adotar", headers={"Authorization": f"Bearer {token}"})
    if resposta.status_code == 200:
        print(f"Problema {problema_id} adotado. Agora rode com --problema {problema_id}.")
    else:
        print(f"Não foi possível adotar ({resposta.status_code}): {resposta.json().get('mensagem', '')}")


def encaminhar(servico_url: str, token: str, problema_id: int) -> None:
    print(f"Chamando {servico_url}/encaminhar/{problema_id}…")
    inicio = time.perf_counter()
    try:
        resposta = httpx.post(f"{servico_url}/encaminhar/{problema_id}",
                              headers={"Authorization": f"Bearer {token}"}, timeout=180)
    except httpx.ConnectError:
        sys.exit(f"O serviço de IA não está rodando em {servico_url}. Suba com: uvicorn app.main:app")
    segundos = time.perf_counter() - inicio
    corpo = resposta.json()
    print(f"HTTP {resposta.status_code} em {segundos:.1f} s\n")
    if resposta.status_code != 200:
        print(corpo.get("detail"))
        return
    resumo = {k: corpo.get(k) for k in ("encontrado", "servico", "categoria", "orgao", "canal", "prazoReferencia",
                                        "textoGerado", "motivoEscolha")}
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    if corpo.get("textoSolicitacao"):
        print(f"\nSolicitação:\n{corpo['textoSolicitacao']}")
    if corpo.get("resumoObservacoes"):
        print(f"\nO que os vizinhos relataram:\n{corpo['resumoObservacoes']}")
    for fonte in corpo.get("fontes", []):
        print(f"\nFonte: {fonte['servico']} — {fonte['url']} (coletada em {fonte['dataColeta']})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--problema", type=int, help="id de um problema adotado para encaminhar")
    grupo.add_argument("--adotar", type=int, help="id de um problema de teste para adotar antes")
    parser.add_argument("--servico", default="http://localhost:8000", help="endereço do serviço de IA")
    args = parser.parse_args()

    with httpx.Client(base_url=config.java_api_url, timeout=config.timeout_java_segundos) as java:
        token = entrar(java)
        if args.adotar:
            adotar(java, token, args.adotar)
        elif args.problema:
            encaminhar(args.servico.rstrip("/"), token, args.problema)
        else:
            listar(java, token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
