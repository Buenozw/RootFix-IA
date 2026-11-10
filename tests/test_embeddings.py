"""Testa o embedder do Gemini sem chamar a API (cliente falso) e a checagem de modelo da base."""

import math

import chromadb
import pytest
from google.genai import errors

from app.busca import BaseIncompativel, Buscador
from app.embeddings import EmbedderGemini, EmbeddingsIndisponiveis


class _Vetor:
    def __init__(self, valores):
        self.values = valores


class _Resposta:
    def __init__(self, n):
        self.embeddings = [_Vetor([3.0, 4.0]) for _ in range(n)]  # norma 5, para testar a normalização


class ClienteFalso:
    """Imita client.models.embed_content e pode falhar nas primeiras chamadas."""

    def __init__(self, falhas: list[int] | None = None):
        self.falhas = list(falhas or [])
        self.chamadas = []
        self.models = self

    def embed_content(self, model, contents, config):
        self.chamadas.append({"model": model, "n": len(contents), "tarefa": config.task_type,
                              "dimensoes": config.output_dimensionality})
        if self.falhas:
            raise errors.APIError(self.falhas.pop(0), {"error": {"message": "falha de teste"}})
        return _Resposta(len(contents))


def novo(cliente, tarefa="RETRIEVAL_QUERY"):
    return EmbedderGemini(tarefa, cliente=cliente, modelo="gemini-embedding-001", dimensoes=768, espera_inicial=0)


def test_envia_tarefa_e_dimensao_e_normaliza():
    cliente = ClienteFalso()
    vetores = novo(cliente, "RETRIEVAL_DOCUMENT")(["a", "b"])
    assert cliente.chamadas == [{"model": "gemini-embedding-001", "n": 2, "tarefa": "RETRIEVAL_DOCUMENT",
                                 "dimensoes": 768}]
    assert all(math.isclose(math.hypot(*v), 1.0) for v in vetores)


def test_divide_em_lotes_de_100():
    cliente = ClienteFalso()
    assert len(novo(cliente)(["x"] * 250)) == 250
    assert [c["n"] for c in cliente.chamadas] == [100, 100, 50]


def test_tenta_de_novo_quando_a_cota_estoura():
    cliente = ClienteFalso(falhas=[429, 503])
    assert len(novo(cliente)(["x"])) == 1
    assert len(cliente.chamadas) == 3


def test_desiste_depois_das_tentativas():
    cliente = ClienteFalso(falhas=[429] * 10)
    with pytest.raises(EmbeddingsIndisponiveis):
        novo(cliente)(["x"])
    assert len(cliente.chamadas) == EmbedderGemini.TENTATIVAS


def test_erro_de_chave_nao_tenta_de_novo():
    cliente = ClienteFalso(falhas=[400])
    with pytest.raises(EmbeddingsIndisponiveis):
        novo(cliente)(["x"])
    assert len(cliente.chamadas) == 1


def test_busca_recusa_base_de_outro_modelo(tmp_path):
    colecao = chromadb.PersistentClient(path=str(tmp_path)).create_collection(
        "teste", metadata={"hnsw:space": "cosine", "embeddings": "local:modelo-x"}, embedding_function=None)
    with pytest.raises(BaseIncompativel):
        Buscador(lambda t: [[1.0]], colecao, assinatura_esperada="gemini:gemini-embedding-001:768")
    Buscador(lambda t: [[1.0]], colecao, assinatura_esperada="local:modelo-x")  # mesma assinatura: ok
