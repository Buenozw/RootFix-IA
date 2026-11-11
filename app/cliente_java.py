"""Busca o problema e as observações na API Java do RootFix, usando o token do próprio gestor.

O serviço de IA não guarda segredo do JWT nem acessa o Oracle: ele repassa o token que o app
mandou, e a API Java decide se aquele usuário pode ver o problema. Assim a regra de acesso
fica num lugar só.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import httpx

from app.config import config
from app.modelos import ProblemaAnonimo

log = logging.getLogger("rootfix-ia.java")


class ErroJava(RuntimeError):
    """A API Java respondeu com erro (401, 403, 404…). Guarda o código e a mensagem dela."""

    def __init__(self, status: int, mensagem: str):
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem


class JavaIndisponivel(RuntimeError):
    """A API Java não respondeu: dormindo no Render (timeout) ou fora do ar."""

    def __init__(self, mensagem: str, por_timeout: bool):
        super().__init__(mensagem)
        self.por_timeout = por_timeout


def _mensagem_de_erro(resposta: httpx.Response) -> str:
    try:
        return resposta.json().get("mensagem") or resposta.reason_phrase
    except ValueError:
        return resposta.reason_phrase or f"HTTP {resposta.status_code}"


class ClienteJava:
    def __init__(self, base_url: str | None = None, timeout: float | None = None,
                 transport: httpx.BaseTransport | None = None):
        self.base_url = (base_url or config.java_api_url).rstrip("/")
        self.timeout = config.timeout_java_segundos if timeout is None else timeout
        self._http = httpx.Client(base_url=self.base_url, timeout=self.timeout, transport=transport)

    def _get(self, caminho: str, token: str):
        try:
            resposta = self._http.get(caminho, headers={"Authorization": f"Bearer {token}"})
        except httpx.TimeoutException as erro:
            raise JavaIndisponivel(
                f"A API do RootFix não respondeu em {self.timeout:.0f} s. No plano gratuito do Render ela dorme "
                "depois de 15 minutos sem uso e leva cerca de 1 minuto para acordar; tente de novo.",
                por_timeout=True,
            ) from erro
        except httpx.HTTPError as erro:
            raise JavaIndisponivel(f"Não foi possível falar com a API do RootFix ({erro.__class__.__name__}).",
                                   por_timeout=False) from erro
        if resposta.status_code >= 400:
            raise ErroJava(resposta.status_code, _mensagem_de_erro(resposta))
        return resposta.json()

    def problema(self, problema_id: int, token: str) -> dict:
        return self._get(f"/problemas/{problema_id}", token)

    def observacoes(self, problema_id: int, token: str) -> list[dict]:
        return self._get(f"/problemas/{problema_id}/observacoes", token)


@lru_cache(maxsize=1)
def cliente_padrao() -> ClienteJava:
    return ClienteJava()


def _nome(objeto) -> str | None:
    return objeto.get("nome") if isinstance(objeto, dict) else None


def para_problema_anonimo(problema: dict, observacoes: list[dict]) -> ProblemaAnonimo:
    """Converte a resposta do Java no que pode ir para o Gemini.

    Fica de fora tudo que identifica pessoas: o `autor` do problema e das observações (id e nome),
    latitude e longitude. A comunidade entra pelo nome, como local aproximado.
    """
    return ProblemaAnonimo(
        titulo=problema.get("titulo") or "",
        descricao=problema.get("descricao") or "",
        categoria=_nome(problema.get("categoria")),
        gravidade=problema.get("gravidadeIa"),
        total_apoios=int(problema.get("totalApoios") or 0),
        comunidade=_nome(problema.get("comunidade")),
        observacoes=[o.get("texto", "") for o in observacoes if o.get("texto")],
    )
