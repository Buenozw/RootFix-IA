"""Serviço de IA do RootFix: Encaminhador do gestor."""

import logging
import os
import time
from collections import defaultdict, deque

from fastapi import FastAPI, Header, HTTPException, Path, Request
from fastapi.middleware.cors import CORSMiddleware

from app.busca import BaseIncompativel
from app.cliente_java import ErroJava, JavaIndisponivel, cliente_padrao, para_problema_anonimo
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
    version="0.3.0",
)

# O app em React Native não precisa de CORS, mas o Expo Web e o Swagger em outro domínio precisam.
# Não há cookie nem sessão (o token vai no cabeçalho), então liberar origens não expõe credenciais.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("CORS_ORIGENS", "*").split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
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


def _token(authorization: str | None) -> str:
    partes = (authorization or "").split()
    if len(partes) != 2 or partes[0].lower() != "bearer" or not partes[1]:
        raise HTTPException(401, "Envie o token do gestor no cabeçalho Authorization: Bearer <token>.")
    return partes[1]


def _erro_do_java(erro: ErroJava) -> HTTPException:
    """Repete o código da API Java (401, 403, 404) com uma mensagem que o app pode mostrar."""
    if erro.status == 401:
        return HTTPException(401, "Sessão expirada ou token inválido. Faça login de novo no app.")
    if erro.status == 403:
        return HTTPException(403, erro.mensagem or "Você não tem acesso a este problema.")
    if erro.status == 404:
        return HTTPException(404, erro.mensagem or "Problema não encontrado.")
    log.warning("API Java respondeu %s", erro.status)
    return HTTPException(502, "A API do RootFix respondeu com um erro inesperado. Tente de novo.")


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


@app.post(
    "/encaminhar/{problema_id}",
    summary="Encaminha um problema adotado, buscando os dados na API Java",
    description="O app manda o id do problema e o token do gestor. O serviço usa o mesmo token para ler o "
    "problema e as observações na API Java, que decide se o gestor tem acesso. Só funciona para problemas "
    "adotados, pedidos pelo gestor da comunidade.",
    response_model=Encaminhamento,
    response_model_by_alias=True,
    responses={
        401: {"description": "Sem token ou token inválido/expirado"},
        403: {"description": "Quem pediu não é o gestor da comunidade do problema"},
        404: {"description": "Problema não existe"},
        409: {"description": "O problema ainda não foi adotado"},
        502: {"description": "API Java fora do ar ou com erro inesperado"},
        503: {"description": "Base de fichas ausente ou busca indisponível"},
        504: {"description": "API Java não respondeu a tempo (Render acordando)"},
    },
)
def encaminhar_problema(
    problema_id: int = Path(gt=0, description="Id do problema na API Java"),
    authorization: str | None = Header(default=None, description="Bearer <token do gestor>"),
) -> Encaminhamento:
    token = _token(authorization)
    java = cliente_padrao()
    try:
        problema = java.problema(problema_id, token)
        if not problema.get("souGestor"):
            raise HTTPException(403, "Só o gestor da comunidade pode encaminhar este problema.")
        if not problema.get("adotado"):
            raise HTTPException(409, "Adote o problema antes de encaminhar.")
        observacoes = java.observacoes(problema_id, token)
    except ErroJava as erro:
        raise _erro_do_java(erro) from erro
    except JavaIndisponivel as erro:
        raise HTTPException(504 if erro.por_timeout else 502, str(erro)) from erro

    resultado = _executar(para_problema_anonimo(problema, observacoes))
    return resultado.model_copy(update={"problema_id": problema_id})
