"""Gera embeddings (vetores) de textos para a busca.

Dois provedores, escolhidos por EMBEDDINGS_PROVEDOR no .env:

- gemini (padrão): modelo gemini-embedding-001 pela API. Não ocupa memória no serviço, por isso
  cabe no plano gratuito do Render (512 MB). Depende da API e da cota gratuita.
- local: modelo multilíngue rodando no próprio computador pelo fastembed. Não depende de API,
  mas usa cerca de 770 MB de memória (medido com scripts/medir_memoria.py), então não cabe no
  Render. Serve para rodar na máquina e para comparar com o Gemini na avaliação.

Vetores de modelos diferentes não se comparam. Por isso a base guarda a "assinatura" do modelo
que a criou, e a busca se recusa a usar uma base feita com outro modelo.
"""

from __future__ import annotations

import logging
import math
import time
from functools import lru_cache
from typing import Protocol

from app.config import RAIZ, config

log = logging.getLogger("rootfix-ia.embeddings")
PASTA_CACHE = RAIZ / ".cache" / "fastembed"


class Embedder(Protocol):
    """Qualquer coisa que transforme textos em vetores. Os testes usam versões falsas."""

    def __call__(self, textos: list[str]) -> list[list[float]]: ...


class EmbeddingsIndisponiveis(RuntimeError):
    """O provedor de embeddings não respondeu (API fora do ar, cota esgotada, sem chave)."""


def assinatura() -> str:
    """Identifica o modelo que gera os vetores, ex.: gemini:gemini-embedding-001:768."""
    if config.embeddings_provedor == "local":
        return f"local:{config.embeddings_modelo}"
    return f"gemini:{config.embeddings_modelo}:{config.embeddings_dimensoes}"


def _normalizar(vetor: list[float]) -> list[float]:
    # Com dimensão reduzida, o Gemini devolve vetores sem norma 1; normalizamos para o cosseno.
    norma = math.sqrt(sum(v * v for v in vetor)) or 1.0
    return [v / norma for v in vetor]


class EmbedderGemini:
    """Chama o gemini-embedding-001. `tarefa` diz ao modelo se o texto é ficha ou pergunta."""

    LOTE_MAXIMO = 100  # textos por chamada
    TENTATIVAS = 5

    def __init__(self, tarefa: str, cliente=None, modelo: str | None = None, dimensoes: int | None = None,
                 espera_inicial: float = 2.0):
        self.tarefa = tarefa  # RETRIEVAL_DOCUMENT para fichas, RETRIEVAL_QUERY para problemas
        self.modelo = modelo or config.embeddings_modelo
        self.dimensoes = dimensoes or config.embeddings_dimensoes
        self.espera_inicial = espera_inicial
        if cliente is None:
            if not config.gemini_configurado:
                raise EmbeddingsIndisponiveis("GEMINI_API_KEY não está configurada no .env.")
            from google import genai

            cliente = genai.Client(api_key=config.gemini_api_key)
        self.cliente = cliente

    def _chamar(self, textos: list[str]) -> list[list[float]]:
        from google.genai import errors, types

        configuracao = types.EmbedContentConfig(task_type=self.tarefa, output_dimensionality=self.dimensoes)
        espera = self.espera_inicial
        for tentativa in range(1, self.TENTATIVAS + 1):
            try:
                resposta = self.cliente.models.embed_content(model=self.modelo, contents=textos, config=configuracao)
                return [_normalizar(list(e.values)) for e in resposta.embeddings]
            except errors.APIError as erro:
                # 429 = cota por minuto; 5xx = instabilidade. Os dois costumam passar esperando.
                temporario = erro.code == 429 or (erro.code or 0) >= 500
                if not temporario or tentativa == self.TENTATIVAS:
                    raise EmbeddingsIndisponiveis(f"Gemini respondeu {erro.code} ao gerar embeddings.") from erro
                log.warning("Gemini respondeu %s; nova tentativa em %.0f s (%d/%d).",
                            erro.code, espera, tentativa, self.TENTATIVAS)
                time.sleep(espera)
                espera *= 2
            except Exception as erro:  # rede, timeout
                raise EmbeddingsIndisponiveis(f"Falha ao falar com o Gemini: {erro.__class__.__name__}.") from erro
        raise EmbeddingsIndisponiveis("Gemini não respondeu.")

    def __call__(self, textos: list[str]) -> list[list[float]]:
        vetores: list[list[float]] = []
        for i in range(0, len(textos), self.LOTE_MAXIMO):
            vetores.extend(self._chamar(textos[i : i + self.LOTE_MAXIMO]))
        return vetores


class EmbedderLocal:
    def __init__(self, modelo: str):
        try:
            from fastembed import TextEmbedding
        except ImportError as erro:
            raise EmbeddingsIndisponiveis(
                "fastembed não está instalado. Rode pip install -r requirements-local.txt."
            ) from erro
        self.modelo = modelo
        self._modelo = TextEmbedding(modelo, cache_dir=str(PASTA_CACHE))

    def __call__(self, textos: list[str]) -> list[list[float]]:
        return [vetor.tolist() for vetor in self._modelo.embed(textos)]


@lru_cache(maxsize=1)
def _local() -> EmbedderLocal:
    return EmbedderLocal(config.embeddings_modelo)


@lru_cache(maxsize=1)
def para_documentos() -> Embedder:
    """Embedder usado na indexação das fichas."""
    return _local() if config.embeddings_provedor == "local" else EmbedderGemini("RETRIEVAL_DOCUMENT")


@lru_cache(maxsize=1)
def para_consultas() -> Embedder:
    """Embedder usado para o texto do problema na hora da busca."""
    return _local() if config.embeddings_provedor == "local" else EmbedderGemini("RETRIEVAL_QUERY")
