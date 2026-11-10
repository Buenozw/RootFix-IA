"""Testa o POST /simular sem chamar o Gemini: o encaminhamento é trocado por versões falsas."""

import pytest
from fastapi.testclient import TestClient

import app.main as principal
from app.embeddings import EmbeddingsIndisponiveis
from app.modelos import Encaminhamento
from app.servico import BaseAusente

cliente = TestClient(principal.app)
CORPO = {"titulo": "Poste apagado", "descricao": "Está apagado há duas semanas.",
         "categoria": "Iluminação pública", "totalApoios": 3, "observacoes": ["Rua escura"]}


@pytest.fixture(autouse=True)
def limpar_limite():
    principal._pedidos_por_ip.clear()
    yield
    principal._pedidos_por_ip.clear()


def test_responde_em_camel_case(monkeypatch):
    recebido = {}

    def falso(problema):
        recebido["problema"] = problema
        return Encaminhamento(encontrado=True, servico="Luz fictícia", texto_solicitacao="Texto",
                              texto_gerado=True, aviso="aviso")

    monkeypatch.setattr(principal, "encaminhar", falso)
    resposta = cliente.post("/simular", json=CORPO)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["textoSolicitacao"] == "Texto" and corpo["textoGerado"] is True
    assert recebido["problema"].total_apoios == 3


def test_valida_a_entrada():
    assert cliente.post("/simular", json={"titulo": "x", "descricao": ""}).status_code == 422


@pytest.mark.parametrize("erro", [BaseAusente("sem base"), EmbeddingsIndisponiveis("cota")])
def test_base_ausente_ou_busca_fora_do_ar_vira_503(monkeypatch, erro):
    def falso(problema):
        raise erro

    monkeypatch.setattr(principal, "encaminhar", falso)
    resposta = cliente.post("/simular", json=CORPO)
    assert resposta.status_code == 503
    assert resposta.json()["detail"]


def test_limite_de_pedidos(monkeypatch):
    monkeypatch.setattr(principal, "encaminhar", lambda p: Encaminhamento(encontrado=False, aviso="a"))
    codigos = [cliente.post("/simular", json=CORPO).status_code for _ in range(principal.LIMITE_SIMULAR + 1)]
    assert codigos[:-1] == [200] * principal.LIMITE_SIMULAR
    assert codigos[-1] == 429
