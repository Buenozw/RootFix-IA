"""Junta as peças: anonimiza o problema, busca as fichas e pede o texto ao Gemini.

Usado pelo POST /simular e, na etapa 6, pelo POST /encaminhar/{id}.
"""

from __future__ import annotations

import logging
import time
from functools import lru_cache

from app.anonimizacao import anonimizar
from app.busca import Buscador
from app.embeddings import assinatura, para_consultas
from app.gerador import Gerador
from app.modelos import Encaminhamento, ProblemaAnonimo


log = logging.getLogger("rootfix-ia.servico")


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


def _base_foi_recriada(erro: Exception) -> bool:
    return erro.__class__.__name__ == "NotFoundError"


def encaminhar(problema: ProblemaAnonimo, buscador: Buscador | None = None,
               gerador: Gerador | None = None) -> Encaminhamento:
    gerador = gerador or gerador_padrao()
    anonimo = anonimizar(problema)
    inicio = time.perf_counter()
    try:
        busca = (buscador or buscador_padrao()).buscar(anonimo.titulo, anonimo.descricao, anonimo.categoria)
    except Exception as erro:
        # Se scripts/indexar.py rodou com o serviço no ar, a base guardada em memória foi apagada.
        # Recarrega a base nova e tenta uma vez, sem precisar reiniciar o servidor.
        if buscador is not None or not _base_foi_recriada(erro):
            raise
        buscador_padrao.cache_clear()
        busca = buscador_padrao().buscar(anonimo.titulo, anonimo.descricao, anonimo.categoria)
    melhor = busca.melhor.similaridade if busca.melhor else None
    log.info("Busca em %.1f s: melhor similaridade %s, limiar %.2f, plano B %s",
             time.perf_counter() - inicio, melhor, busca.limiar, busca.caiu_no_plano_b)
    return gerador.encaminhar(anonimo, busca)
