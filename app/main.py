"""Serviço de IA do RootFix: Encaminhador do gestor."""

import logging
import time
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Request

from app.busca import BaseIncompativel
from app.config import config
from app.embeddings import EmbeddingsIndisponiveis, assinatura
from app.modelos import Encaminhamento, ProblemaAnonimo, SimularRequest
from app.servico import BaseAusente, encaminhar

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("rootfix-ia")

app = FastAPI(
    title="RootFix IA · Encaminhador do gestor",
    description="Diz ao gestor qual serviço da prefeitura resolve um problema adotado e escreve a solicitação, "
    "com base em fichas públicas do SP156 (RAG) e no Gemini.",
    version="0.2.0",
)

# Limite simples para o /simular, que não exige login: protege a cota gratuita do Gemini
LIMITE_SIMULAR = 10  # pedidos
JANELA_SEGUNDOS = 60
_pedidos_por_ip: dict[str, deque] = defaultdict(deque)


def _respeitar_limite(ip: str) -> None:
    agora = time.monotonic()
    fila = _pedidos_por_ip[ip]
    while fila and agora - fila[0] > JANELA_SEGUNDOS:
        fila.popleft()
    if len(fila) >= LIMITE_SIMULAR:
        raise HTTPException(429, f"Limite de {LIMITE_SIMULAR} simulações por minuto atingido. Tente daqui a pouco.")
    fila.append(agora)


def _executar(problema: ProblemaAnonimo) -> Encaminhamento:
    inicio = time.perf_counter()
    try:
        resultado = encaminhar(problema)
    except BaseAusente as erro:
        raise HTTPException(503, str(erro)) from erro
    except BaseIncompativel as erro:
        raise HTTPException(503, str(erro)) from erro
    except EmbeddingsIndisponiveis as erro:
        log.warning("Busca indisponível: %s", erro)
        raise HTTPException(503, "A busca nas fichas está indisponível no momento (Gemini). "
                                 "Tente de novo em alguns minutos.") from erro
    # Log só com o resultado e o tempo: nunca o texto do problema
    log.info("Encaminhamento: encontrado=%s texto_gerado=%s em %.1f s",
             resultado.encontrado, resultado.texto_gerado, time.perf_counter() - inicio)
    return resultado


def estado_da_base() -> tuple[int, str | None]:
    """Quantos trechos existem na base e com que modelo ela foi criada. (0, None) se não existe."""
    if not any(config.pasta_vetores.glob("*.sqlite3")):
        return 0, None
    try:
        import chromadb

        colecao = chromadb.PersistentClient(path=str(config.pasta_vetores)).get_collection(config.nome_colecao)
        return colecao.count(), (colecao.metadata or {}).get("embeddings")
    except Exception as erro:  # base corrompida ou coleção ainda não criada
        log.warning("Não foi possível ler a base vetorial: %s", erro.__class__.__name__)
        return 0, None


@app.get("/health", summary="Saúde do serviço")
def health() -> dict:
    trechos, criada_com = estado_da_base()
    em_uso = assinatura()
    return {
        "status": "ok",
        "versao": app.version,
        "trechosNaBase": trechos,
        "baseIndexada": trechos > 0,
        "embeddings": em_uso,
        "baseCriadaCom": criada_com,
        "baseCompativel": trechos > 0 and criada_com == em_uso,
        "geminiConfigurado": config.gemini_configurado,
        "geminiModelo": config.gemini_modelo,
        "javaApiUrl": config.java_api_url,
    }


@app.post(
    "/simular",
    summary="Encaminha um problema escrito à mão, sem passar pela API Java",
    description="Mesmo processamento do encaminhamento real, a partir de dados digitados. Serve para a "
    "avaliação e para demonstrar quando a API Java está dormindo. Limite de 10 pedidos por minuto.",
    response_model=Encaminhamento,
    response_model_by_alias=True,
    responses={429: {"description": "Limite de pedidos atingido"},
               503: {"description": "Base de fichas ausente ou busca indisponível"}},
)
def simular(dados: SimularRequest, request: Request) -> Encaminhamento:
    _respeitar_limite(request.client.host if request.client else "desconhecido")
    return _executar(ProblemaAnonimo(**dados.model_dump()))
