"""Junta as peças: anonimiza o problema, busca as fichas e pede o texto ao Gemini.

Usado pelo POST /simular e, na etapa 6, pelo POST /encaminhar/{id}.
"""

from __future__ import annotations

from functools import lru_cache

from app.anonimizacao import anonimizar
from app.busca import Buscador
from app.embeddings import assinatura, para_consultas
from app.gerador import Gerador
from app.modelos import Encaminhamento, ProblemaAnonimo


class BaseAusente(RuntimeError):
    """A base de fichas ainda não foi criada com scripts/indexar.py."""


@lru_cache(maxsize=1)
def buscador_padrao() -> Buscador:
    import chromadb

    from app.config import config

    try:
        colecao = chromadb.PersistentClient(path=str(config.pasta_vetores)).get_collection(config.nome_colecao)
    except Exception as erro:
        raise BaseAusente("A base de fichas ainda não foi criada. Rode python scripts/indexar.py.") from erro
    return Buscador(para_consultas(), colecao, assinatura_esperada=assinatura())


@lru_cache(maxsize=1)
def gerador_padrao() -> Gerador:
    return Gerador()


def encaminhar(problema: ProblemaAnonimo, buscador: Buscador | None = None,
               gerador: Gerador | None = None) -> Encaminhamento:
    buscador = buscador or buscador_padrao()
    gerador = gerador or gerador_padrao()
    anonimo = anonimizar(problema)
    busca = buscador.buscar(anonimo.titulo, anonimo.descricao, anonimo.categoria)
    return gerador.encaminhar(anonimo, busca)
