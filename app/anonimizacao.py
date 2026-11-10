"""Tira dados pessoais do texto antes de mandar qualquer coisa para o Gemini.

Nomes de quem publicou ou comentou nem chegam aqui: os campos de autor são descartados antes.
Este módulo cuida do que pode aparecer no texto livre escrito pelos moradores.
"""

from __future__ import annotations

import re

from app.modelos import ProblemaAnonimo

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
# Telefones brasileiros: (11) 91234-5678, 11 912345678, +55 11 3456-7890, 0800 123 4567…
_TELEFONE = re.compile(r"(?<!\w)(\+?55[\s-]?)?(\(?\d{2}\)?[\s-]?)?\d{4,5}[\s-]?\d{4}(?!\w)|\b0800[\s-]?\d{3}[\s-]?\d{4}\b")
# "Rua X, 123", "Av. Paulista, 1000 - apto 12": troca só o número da casa e o complemento
_NUMERO_DA_CASA = re.compile(
    r"\b((?:rua|r\.|avenida|av\.?|alameda|al\.|travessa|tv\.|estrada|praça)\s+[^\d,\n]{2,60}?),?\s*(?:n[ºo°.]?\s*)?\d{1,5}"
    r"(?:\s*[-,]?\s*(?:apto?\.?|apartamento|casa|bloco|bl\.?)\s*\w+)?",
    re.IGNORECASE,
)


def anonimizar_texto(texto: str | None) -> str:
    if not texto:
        return ""
    texto = _EMAIL.sub("[e-mail removido]", texto)
    texto = _CPF.sub("[documento removido]", texto)
    texto = _TELEFONE.sub("[telefone removido]", texto)
    texto = _NUMERO_DA_CASA.sub(lambda m: f"{m.group(1)}, [número removido]", texto)
    return texto.strip()


def anonimizar(problema: ProblemaAnonimo) -> ProblemaAnonimo:
    return problema.model_copy(update={
        "titulo": anonimizar_texto(problema.titulo),
        "descricao": anonimizar_texto(problema.descricao),
        "observacoes": [t for t in (anonimizar_texto(o) for o in problema.observacoes) if t],
    })
