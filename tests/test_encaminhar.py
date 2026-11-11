"""Testa o POST /encaminhar/{id} com uma API Java FALSA (httpx.MockTransport), sem chamar o Render.

Os dados do problema e das observações são fictícios.
"""

import httpx
import pytest
from fastapi.testclient import TestClient

import app.main as principal
from app.cliente_java import ClienteJava, para_problema_anonimo
from app.modelos import Encaminhamento

TOKEN = "token-de-teste"

PROBLEMA = {
    "id": 42, "titulo": "Poste apagado", "descricao": "Apagado há duas semanas.",
    "latitude": -23.56, "longitude": -46.65,
    "autor": {"id": 7, "nome": "Maria Fictícia"},
    "comunidade": {"id": 1, "nome": "Comunidade Fictícia"},
    "categoria": {"id": 2, "nome": "Iluminação pública"},
    "adotado": True, "status": "PENDENTE", "gravidadeIa": "MEDIA", "justificativaIa": "Poste apagado na foto.",
    "totalApoios": 5, "souGestor": True,
}
OBSERVACOES = [
    {"id": 1, "texto": "À noite fica um breu", "autor": {"id": 8, "nome": "José Fictício"}},
    {"id": 2, "texto": "Me liga no (11) 91234-5678", "autor": {"id": 9, "nome": "Ana Fictícia"}},
]


def java_falso(problema=None, status=200, mensagem="", erro_rede=None):
    """Cria um cliente para uma API Java falsa e guarda o que foi pedido a ela."""
    pedidos = []

    def responder(request: httpx.Request) -> httpx.Response:
        pedidos.append(request)
        if erro_rede:
            raise erro_rede
        if status >= 400:
            return httpx.Response(status, json={"status": status, "mensagem": mensagem})
        if request.url.path.endswith("/observacoes"):
            return httpx.Response(200, json=OBSERVACOES)
        return httpx.Response(200, json=problema or PROBLEMA)

    return ClienteJava("https://java.invalid", timeout=5, transport=httpx.MockTransport(responder)), pedidos


@pytest.fixture
def api(monkeypatch):
    """Cliente do serviço com a API Java falsa e o encaminhamento (busca + Gemini) trocado por um falso."""
    recebido = {}

    def preparar(**kwargs):
        cliente, pedidos = java_falso(**kwargs)
        monkeypatch.setattr(principal, "cliente_padrao", lambda: cliente)
        recebido["pedidos"] = pedidos
        return recebido

    def encaminhar_falso(problema):
        recebido["problema"] = problema
        return Encaminhamento(encontrado=True, servico="Luz fictícia", texto_solicitacao="Texto",
                              texto_gerado=True, aviso="a")

    monkeypatch.setattr(principal, "encaminhar", encaminhar_falso)
    return TestClient(principal.app), preparar


def post(cliente, problema_id=42, token=TOKEN):
    cabecalhos = {"Authorization": f"Bearer {token}"} if token else {}
    return cliente.post(f"/encaminhar/{problema_id}", headers=cabecalhos)


def test_encaminha_problema_adotado(api):
    cliente, preparar = api
    recebido = preparar()
    resposta = post(cliente)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["problemaId"] == 42 and corpo["servico"] == "Luz fictícia"
    # o mesmo token do gestor foi repassado ao Java, nas duas chamadas
    assert [p.url.path for p in recebido["pedidos"]] == ["/problemas/42", "/problemas/42/observacoes"]
    assert all(p.headers["Authorization"] == f"Bearer {TOKEN}" for p in recebido["pedidos"])


def test_nenhum_nome_de_autor_chega_ao_encaminhamento(api):
    cliente, preparar = api
    recebido = preparar()
    post(cliente)
    problema = recebido["problema"]
    tudo = problema.model_dump_json()
    for nome in ("Maria Fictícia", "José Fictício", "Ana Fictícia"):
        assert nome not in tudo
    assert "-46.65" not in tudo  # coordenadas também ficam de fora
    assert problema.comunidade == "Comunidade Fictícia" and problema.total_apoios == 5
    assert problema.categoria == "Iluminação pública" and problema.gravidade == "MEDIA"


def test_conversao_descarta_autores_e_coordenadas():
    anonimo = para_problema_anonimo(PROBLEMA, OBSERVACOES)
    assert anonimo.observacoes == ["À noite fica um breu", "Me liga no (11) 91234-5678"]
    assert not hasattr(anonimo, "autor") and not hasattr(anonimo, "latitude")


def test_sem_token_e_401(api):
    cliente, preparar = api
    preparar()
    assert post(cliente, token=None).status_code == 401
    assert cliente.post("/encaminhar/42", headers={"Authorization": "Basic abc"}).status_code == 401


def test_problema_nao_adotado_e_409(api):
    cliente, preparar = api
    recebido = preparar(problema={**PROBLEMA, "adotado": False})
    resposta = post(cliente)
    assert resposta.status_code == 409
    assert "Adote" in resposta.json()["detail"]
    assert "problema" not in recebido  # não chegou a buscar nem a chamar o Gemini


def test_quem_nao_e_gestor_recebe_403(api):
    cliente, preparar = api
    preparar(problema={**PROBLEMA, "souGestor": False})
    assert post(cliente).status_code == 403


@pytest.mark.parametrize("status_java,esperado", [(401, 401), (403, 403), (404, 404), (500, 502)])
def test_erros_do_java_viram_erros_claros(api, status_java, esperado):
    cliente, preparar = api
    preparar(status=status_java, mensagem="Mensagem do Java")
    resposta = post(cliente)
    assert resposta.status_code == esperado
    assert resposta.json()["detail"]


def test_render_dormindo_vira_504(api):
    cliente, preparar = api
    preparar(erro_rede=httpx.ReadTimeout("demorou"))
    resposta = post(cliente)
    assert resposta.status_code == 504
    assert "Render" in resposta.json()["detail"]


def test_java_fora_do_ar_vira_502(api):
    cliente, preparar = api
    preparar(erro_rede=httpx.ConnectError("recusada"))
    assert post(cliente).status_code == 502


def test_id_invalido_e_422(api):
    cliente, preparar = api
    preparar()
    assert post(cliente, problema_id=0).status_code == 422
