"""Lê as configurações do arquivo .env (ou das variáveis de ambiente do Render)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")


def _numero(nome: str, padrao: float) -> float:
    valor = os.getenv(nome, "").strip()
    return float(valor) if valor else padrao


@dataclass(frozen=True)
class Config:
    gemini_api_key: str
    gemini_modelo: str
    java_api_url: str
    embeddings_modelo: str
    limiar_similaridade: float
    timeout_java_segundos: float
    timeout_gemini_segundos: float
    pasta_vetores: Path
    nome_colecao: str = "fichas_156"

    @property
    def gemini_configurado(self) -> bool:
        return bool(self.gemini_api_key)


def carregar() -> Config:
    return Config(
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_modelo=os.getenv("GEMINI_MODELO", "").strip(),
        java_api_url=os.getenv("JAVA_API_URL", "https://rootfix-java.onrender.com").strip().rstrip("/"),
        embeddings_modelo=os.getenv(
            "EMBEDDINGS_MODELO", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        ).strip(),
        # Valor provisório: o limiar definitivo sai da avaliação da busca (etapa 4)
        limiar_similaridade=_numero("LIMIAR_SIMILARIDADE", 0.5),
        timeout_java_segundos=_numero("TIMEOUT_JAVA_SEGUNDOS", 75),
        timeout_gemini_segundos=_numero("TIMEOUT_GEMINI_SEGUNDOS", 30),
        pasta_vetores=RAIZ / "data" / "vetores",
    )


config = carregar()
