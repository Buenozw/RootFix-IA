"""Avalia a busca (a parte de RAG) com os casos de data/avaliacao/casos.jsonl.

Uso:  python scripts/avaliar_busca.py
Precisa da base criada pelo scripts/indexar.py. Grava os números em docs/avaliacao.md
(entre as marcas da seção de busca) e o detalhe por caso em data/avaliacao/resultado_busca.json.

O que mede:
- acerto da categoria e do serviço no 1º lugar (top-1) e entre os 3 primeiros (top-3);
- MRR (média de 1/posição do serviço certo: 1 = sempre em 1º, 0,5 = em média em 2º);
- efeito do filtro por categoria (com e sem filtro) e do plano B quando o Spring AI erra;
- limiar de "não encontrei": para cada valor, quantos casos válidos passam e quantos casos
  fora do catálogo são recusados.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.busca import Buscador, ResultadoBusca  # noqa: E402
from app.fichas import CATEGORIAS  # noqa: E402

CASOS = RAIZ / "data" / "avaliacao" / "casos.jsonl"
RESULTADO = RAIZ / "data" / "avaliacao" / "resultado_busca.json"
RELATORIO = RAIZ / "docs" / "avaliacao.md"
INICIO, FIM = "<!-- busca:inicio -->", "<!-- busca:fim -->"
LIMIARES = [round(0.30 + 0.05 * i, 2) for i in range(11)]  # 0,30 a 0,80


def carregar_casos(arquivo: Path = CASOS) -> list[dict]:
    with arquivo.open(encoding="utf-8") as entrada:
        return [json.loads(linha) for linha in entrada if linha.strip()]


def _posicao(resultado: ResultadoBusca, campo: str, esperado: str) -> int | None:
    """Posição (1, 2, 3…) do valor esperado entre os candidatos, ou None se não aparece."""
    for i, candidato in enumerate(resultado.candidatos, start=1):
        if getattr(candidato, campo).strip().lower() == esperado.strip().lower():
            return i
    return None


def _pct(parte: int, total: int) -> str:
    return f"{100 * parte / total:.0f}%" if total else "—"


def metricas_de_acerto(casos: list[dict], resultados: dict[str, ResultadoBusca]) -> dict:
    validos = [c for c in casos if c["deveria_encontrar"] and c.get("categoria_esperada")]
    com_servico = [c for c in validos if c.get("servico_esperado")]

    cat_top1 = cat_top3 = 0
    por_categoria: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for caso in validos:
        pos = _posicao(resultados[caso["id"]], "categoria", caso["categoria_esperada"])
        cat_top1 += pos == 1
        cat_top3 += pos is not None and pos <= 3
        por_categoria[caso["categoria_esperada"]][0] += pos == 1
        por_categoria[caso["categoria_esperada"]][1] += 1

    srv_top1 = srv_top3 = 0
    soma_rr = 0.0
    for caso in com_servico:
        pos = _posicao(resultados[caso["id"]], "servico", caso["servico_esperado"])
        srv_top1 += pos == 1
        srv_top3 += pos is not None and pos <= 3
        soma_rr += 1 / pos if pos else 0

    return {
        "casos_validos": len(validos),
        "categoria_top1": cat_top1,
        "categoria_top3": cat_top3,
        "casos_com_servico": len(com_servico),
        "servico_top1": srv_top1,
        "servico_top3": srv_top3,
        "mrr": round(soma_rr / len(com_servico), 3) if com_servico else None,
        "por_categoria": {c: por_categoria[c] for c in CATEGORIAS if c in por_categoria},
    }


def varrer_limiares(casos: list[dict], buscar_com_limiar) -> list[dict]:
    """Para cada limiar, conta acertos aceitos, falsos negativos, recusas certas e falsos positivos."""
    linhas = []
    for limiar in LIMIARES:
        vp = fn = vn = fp = 0
        for caso in casos:
            resultado = buscar_com_limiar(caso, limiar)
            certo = resultado.melhor is not None and caso.get("categoria_esperada") and \
                resultado.melhor.categoria == caso["categoria_esperada"]
            if caso["deveria_encontrar"]:
                if resultado.encontrado and certo:
                    vp += 1
                else:
                    fn += 1
            else:
                if resultado.encontrado:
                    fp += 1
                else:
                    vn += 1
        sensibilidade = vp / (vp + fn) if vp + fn else 0
        especificidade = vn / (vn + fp) if vn + fp else 0
        linhas.append({
            "limiar": limiar, "aceitos_certos": vp, "falsos_negativos": fn,
            "recusas_certas": vn, "falsos_positivos": fp,
            "equilibrio": round((sensibilidade + especificidade) / 2, 3),
        })
    return linhas


def avaliar(casos: list[dict], buscador: Buscador) -> dict:
    memo: dict[tuple, ResultadoBusca] = {}

    def buscar(caso: dict, usar_filtro: bool = True, limiar: float | None = None) -> ResultadoBusca:
        chave = (caso["id"], usar_filtro, limiar)
        if chave not in memo:
            original = buscador.limiar
            if limiar is not None:
                buscador.limiar = limiar
            memo[chave] = buscador.buscar(caso["titulo"], caso["descricao"], caso.get("categoria_spring"), usar_filtro)
            buscador.limiar = original
        return memo[chave]

    com_filtro = {c["id"]: buscar(c, True) for c in casos}
    sem_filtro = {c["id"]: buscar(c, False) for c in casos}
    errados = [c for c in casos if c["tipo"] == "categoria_errada"]

    varredura = varrer_limiares(casos, lambda caso, limiar: buscar(caso, True, limiar))
    melhor = max(varredura, key=lambda linha: (linha["equilibrio"], -linha["falsos_positivos"]))

    detalhe = []
    for caso in casos:
        r = com_filtro[caso["id"]]
        detalhe.append({
            "id": caso["id"], "tipo": caso["tipo"], "titulo": caso["titulo"],
            "categoria_esperada": caso.get("categoria_esperada"),
            "servico_esperado": caso.get("servico_esperado"),
            "deveria_encontrar": caso["deveria_encontrar"],
            "encontrado": r.encontrado, "plano_b": r.caiu_no_plano_b,
            "top3": [{"servico": c.servico, "categoria": c.categoria, "similaridade": c.similaridade}
                     for c in r.candidatos[:3]],
        })

    return {
        "limiar_atual": buscador.limiar,
        "total_casos": len(casos),
        "nao_revisados": sum(1 for c in casos if not c.get("revisado")),
        "com_filtro": metricas_de_acerto(casos, com_filtro),
        "sem_filtro": metricas_de_acerto(casos, sem_filtro),
        "plano_b": {
            "casos_categoria_errada": len(errados),
            "acionado": sum(com_filtro[c["id"]].caiu_no_plano_b for c in errados),
            "categoria_certa_no_fim": sum(
                bool(com_filtro[c["id"]].melhor) and com_filtro[c["id"]].melhor.categoria == c["categoria_esperada"]
                for c in errados),
        },
        "varredura": varredura,
        "limiar_sugerido": melhor["limiar"],
        "detalhe": detalhe,
    }


def relatorio(r: dict) -> str:
    cf, sf = r["com_filtro"], r["sem_filtro"]
    linhas = [INICIO, "", "## Avaliação da busca (RAG)", ""]
    if r["nao_revisados"]:
        linhas += [f"> **Atenção:** {r['nao_revisados']} de {r['total_casos']} casos ainda não tiveram o rótulo "
                   "revisado (`revisado: false` em `casos.jsonl`). Os números abaixo são provisórios.", ""]
    if not cf["casos_com_servico"]:
        linhas += ["> O acerto por **serviço** e o MRR aparecem depois que `servico_esperado` for preenchido "
                   "nos casos, com o nome exato do serviço da ficha.", ""]
    linhas += [
        f"{r['total_casos']} casos, {cf['casos_validos']} com serviço esperado na base. "
        f"Limiar usado: {r['limiar_atual']:.2f}.", "",
        "| Métrica | Com filtro por categoria | Sem filtro |",
        "|---|---|---|",
        f"| Categoria certa em 1º | {_pct(cf['categoria_top1'], cf['casos_validos'])} | "
        f"{_pct(sf['categoria_top1'], sf['casos_validos'])} |",
        f"| Categoria certa no top-3 | {_pct(cf['categoria_top3'], cf['casos_validos'])} | "
        f"{_pct(sf['categoria_top3'], sf['casos_validos'])} |",
        f"| Serviço certo em 1º | {_pct(cf['servico_top1'], cf['casos_com_servico'])} | "
        f"{_pct(sf['servico_top1'], sf['casos_com_servico'])} |",
        f"| Serviço certo no top-3 | {_pct(cf['servico_top3'], cf['casos_com_servico'])} | "
        f"{_pct(sf['servico_top3'], sf['casos_com_servico'])} |",
        f"| MRR do serviço | {cf['mrr'] if cf['mrr'] is not None else '—'} | {sf['mrr'] if sf['mrr'] is not None else '—'} |",
        "",
        "### Acerto da categoria em 1º, por categoria", "",
        "| Categoria | Acertos | Casos |", "|---|---|---|",
    ]
    for categoria, (acertos, total) in cf["por_categoria"].items():
        linhas.append(f"| {categoria} | {acertos} | {total} |")

    pb = r["plano_b"]
    linhas += [
        "", "### Quando o Spring AI erra a categoria", "",
        f"Em {pb['casos_categoria_errada']} casos com a categoria errada de propósito, a busca filtrada ficou "
        f"abaixo do limiar e caiu no plano B (base toda) em {pb['acionado']}; a categoria certa terminou em 1º "
        f"em {pb['categoria_certa_no_fim']}.", "",
        "### Escolha do limiar de \"não encontrei\"", "",
        "| Limiar | Aceitos certos | Falsos negativos | Recusas certas | Falsos positivos | Equilíbrio |",
        "|---|---|---|---|---|---|",
    ]
    for v in r["varredura"]:
        marca = " ← sugerido" if v["limiar"] == r["limiar_sugerido"] else ""
        linhas.append(f"| {v['limiar']:.2f}{marca} | {v['aceitos_certos']} | {v['falsos_negativos']} | "
                      f"{v['recusas_certas']} | {v['falsos_positivos']} | {v['equilibrio']:.2f} |")
    linhas += [
        "", "*Equilíbrio* é a média entre a taxa de casos válidos aceitos com a categoria certa e a taxa de casos "
        "fora do catálogo recusados. O limiar sugerido é o de maior equilíbrio; num empate, o que tem menos "
        "falsos positivos, porque responder errado com confiança é pior para o gestor do que dizer que não "
        "encontrou.", "",
        "### Casos que falharam", "",
        "| Caso | Tipo | Esperado | 1º lugar | Similaridade |", "|---|---|---|---|---|",
    ]
    falhas = 0
    for d in r["detalhe"]:
        top = d["top3"][0] if d["top3"] else None
        if d["deveria_encontrar"]:
            falhou = not d["encontrado"] or not top or top["categoria"] != d["categoria_esperada"]
            esperado = d["categoria_esperada"]
        else:
            falhou = d["encontrado"]
            esperado = "não encontrar"
        if falhou:
            falhas += 1
            linhas.append(f"| {d['id']} {d['titulo']} | {d['tipo']} | {esperado} | "
                          f"{top['servico'] + ' (' + top['categoria'] + ')' if top else '—'} | "
                          f"{top['similaridade'] if top else '—'} |")
    if not falhas:
        linhas.append("| — | — | — | nenhuma falha | — |")
    linhas += ["", FIM]
    return "\n".join(linhas)


def gravar_relatorio(texto: str, arquivo: Path = RELATORIO, inicio: str = INICIO, fim: str = FIM) -> None:
    """Troca só a seção entre as marcas; o resto do arquivo (texto escrito à mão) fica igual."""
    atual = arquivo.read_text(encoding="utf-8") if arquivo.exists() else "# Avaliação\n\n"
    if inicio in atual and fim in atual:
        antes, _, resto = atual.partition(inicio)
        _, _, depois = resto.partition(fim)
        novo = antes + texto + depois
    else:
        novo = atual.rstrip() + "\n\n" + texto + "\n"
    arquivo.write_text(novo, encoding="utf-8")


def main() -> int:
    import chromadb

    from app.config import config
    from app.busca import BaseIncompativel
    from app.embeddings import EmbeddingsIndisponiveis, assinatura, para_consultas

    casos = carregar_casos()
    try:
        colecao = chromadb.PersistentClient(path=str(config.pasta_vetores)).get_collection(config.nome_colecao)
        if colecao.count() == 0:
            raise ValueError("base vazia")
    except Exception:
        print("Não encontrei a base vetorial ou ela está vazia. Rode python scripts/indexar.py antes.")
        return 1

    print(f"Buscando com {assinatura()}…")
    try:
        r = avaliar(casos, Buscador(para_consultas(), colecao, assinatura_esperada=assinatura()))
    except (BaseIncompativel, EmbeddingsIndisponiveis) as erro:
        print(erro)
        return 1
    RESULTADO.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    gravar_relatorio(relatorio(r))

    cf = r["com_filtro"]
    print(f"Casos: {r['total_casos']}  ·  não revisados: {r['nao_revisados']}")
    print(f"Categoria certa em 1º: {_pct(cf['categoria_top1'], cf['casos_validos'])}  ·  "
          f"no top-3: {_pct(cf['categoria_top3'], cf['casos_validos'])}")
    if cf["casos_com_servico"]:
        print(f"Serviço certo em 1º: {_pct(cf['servico_top1'], cf['casos_com_servico'])}  ·  MRR: {cf['mrr']}")
    print(f"Limiar sugerido: {r['limiar_sugerido']:.2f} (atual: {r['limiar_atual']:.2f}). "
          "Para usar, coloque LIMIAR_SIMILARIDADE no .env.")
    print(f"Relatório: {RELATORIO.relative_to(RAIZ)}  ·  detalhe: {RESULTADO.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
