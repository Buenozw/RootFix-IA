"""Serviço de IA do RootFix: Encaminhador do gestor."""

import logging

from fastapi import FastAPI

from app.config import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("rootfix-ia")

app = FastAPI(
    title="RootFix IA · Encaminhador do gestor",
    description="Diz ao gestor qual serviço da prefeitura resolve um problema adotado e escreve a solicitação, "
    "com base em fichas públicas do SP156 (RAG) e no Gemini.",
    version="0.1.0",
)


def contar_trechos() -> int:
    """Quantos trechos de fichas existem na base vetorial. Zero se a base ainda não foi criada."""
    if not any(config.pasta_vetores.glob("*.sqlite3")):
        return 0
    try:
        import chromadb

        cliente = chromadb.PersistentClient(path=str(config.pasta_vetores))
        return cliente.get_collection(config.nome_colecao).count()
    except Exception as erro:  # base corrompida ou coleção ainda não criada
        log.warning("Não foi possível ler a base vetorial: %s", erro.__class__.__name__)
        return 0


@app.get("/health", summary="Saúde do serviço")
def health() -> dict:
    trechos = contar_trechos()
    return {
        "status": "ok",
        "versao": app.version,
        "trechosNaBase": trechos,
        "baseIndexada": trechos > 0,
        "geminiConfigurado": config.gemini_configurado,
        "geminiModelo": config.gemini_modelo or None,
        "embeddingsModelo": config.embeddings_modelo,
        "javaApiUrl": config.java_api_url,
    }
