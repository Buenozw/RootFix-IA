"""Gera embeddings (vetores) de textos com um modelo local e multilíngue.

Usamos o fastembed, que roda o modelo em ONNX sem PyTorch: cabe na memória do plano
gratuito do Render. O modelo é baixado do Hugging Face na primeira vez e fica em cache.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Protocol

from app.config import RAIZ, config

PASTA_CACHE = RAIZ / ".cache" / "fastembed"


class Embedder(Protocol):
    """Qualquer coisa que transforme textos em vetores. Os testes usam uma versão falsa."""

    def __call__(self, textos: list[str]) -> list[list[float]]: ...


class EmbedderLocal:
    def __init__(self, modelo: str):
        from fastembed import TextEmbedding

        self.modelo = modelo
        self._modelo = TextEmbedding(modelo, cache_dir=str(PASTA_CACHE))

    def __call__(self, textos: list[str]) -> list[list[float]]:
        return [vetor.tolist() for vetor in self._modelo.embed(textos)]


@lru_cache(maxsize=1)
def padrao() -> EmbedderLocal:
    """Carrega o modelo uma vez só por processo (carregar leva alguns segundos)."""
    return EmbedderLocal(config.embeddings_modelo)
