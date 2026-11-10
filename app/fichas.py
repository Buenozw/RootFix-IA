"""Leitura e validação das fichas de serviço coletadas em data/raw/.

Cada ficha é um arquivo .md com um cabeçalho YAML (entre linhas ---) e, depois dele,
o texto copiado da fonte oficial. Este módulo é usado pelo validador e pela indexação.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# As 8 categorias cadastradas na API Java (tabela RF_CATEGORIA)
CATEGORIAS = [
    "Buraco ou pavimento",
    "Iluminação pública",
    "Lixo e limpeza",
    "Bueiro e drenagem",
    "Calçada e acessibilidade",
    "Sinalização de trânsito",
    "Praças e áreas verdes",
    "Outros",
]

OBRIGATORIOS = ["servico", "categoria_rootfix", "fonte_url", "data_coleta"]
OPCIONAIS = ["orgao", "canal", "prazo_referencia", "documentos_necessarios", "termos_populares", "subprefeitura"]
TEXTO_MINIMO = 150  # caracteres; menos que isso não dá contexto para a busca
IDADE_MAXIMA_DIAS = 60

# Sinais de que um campo ainda está com o texto do modelo
_PLACEHOLDER = re.compile(r"<[^>]*>|COLE AQUI|substituir|PREENCHER", re.IGNORECASE)


@dataclass
class Ficha:
    arquivo: Path
    cabecalho: dict = field(default_factory=dict)
    texto: str = ""
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    ignorada: str | None = None  # motivo quando a ficha é pulada de propósito (modelo ou exemplo)

    @property
    def valida(self) -> bool:
        return self.ignorada is None and not self.erros

    @property
    def categoria(self) -> str | None:
        return self.cabecalho.get("categoria_rootfix")


def _separar(conteudo: str) -> tuple[str | None, str]:
    """Devolve (cabeçalho YAML, texto). Cabeçalho None se o arquivo não começa com ---."""
    linhas = conteudo.lstrip("﻿").splitlines()
    if not linhas or linhas[0].strip() != "---":
        return None, conteudo
    for i in range(1, len(linhas)):
        if linhas[i].strip() == "---":
            return "\n".join(linhas[1:i]), "\n".join(linhas[i + 1 :]).strip()
    return None, conteudo


def _como_data(valor) -> dt.date | None:
    if isinstance(valor, dt.datetime):
        return valor.date()
    if isinstance(valor, dt.date):
        return valor
    try:
        return dt.date.fromisoformat(str(valor).strip())
    except ValueError:
        return None


def _vazio(valor) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip()) or valor == []


def ler(arquivo: Path, hoje: dt.date | None = None) -> Ficha:
    hoje = hoje or dt.date.today()
    ficha = Ficha(arquivo=arquivo)

    if arquivo.name.startswith("_"):
        ficha.ignorada = "modelo (arquivo começa com _)"
        return ficha

    bruto, texto = _separar(arquivo.read_text(encoding="utf-8"))
    ficha.texto = texto
    if bruto is None:
        ficha.erros.append("Sem cabeçalho: o arquivo precisa começar com --- e ter outro --- depois dos campos.")
        return ficha
    try:
        cabecalho = yaml.safe_load(bruto) or {}
    except yaml.YAMLError as erro:
        linha = getattr(getattr(erro, "problem_mark", None), "line", None)
        onde = f" (perto da linha {linha + 2})" if linha is not None else ""
        ficha.erros.append(f"Cabeçalho com erro de formatação{onde}. Confira dois-pontos e aspas.")
        return ficha
    if not isinstance(cabecalho, dict):
        ficha.erros.append("Cabeçalho inválido: cada linha deve ser 'campo: valor'.")
        return ficha
    ficha.cabecalho = cabecalho

    if cabecalho.get("exemplo") is True:
        ficha.ignorada = "exemplo (exemplo: true)"
        return ficha

    for campo in OBRIGATORIOS:
        if _vazio(cabecalho.get(campo)):
            ficha.erros.append(f"Campo obrigatório vazio: {campo}.")

    desconhecidos = set(cabecalho) - set(OBRIGATORIOS) - set(OPCIONAIS)
    if desconhecidos:
        ficha.avisos.append(f"Campos que a indexação vai ignorar: {', '.join(sorted(desconhecidos))}.")

    categoria = cabecalho.get("categoria_rootfix")
    if not _vazio(categoria) and categoria not in CATEGORIAS:
        ficha.erros.append(f"categoria_rootfix '{categoria}' não existe. Use uma destas: {'; '.join(CATEGORIAS)}.")

    url = cabecalho.get("fonte_url")
    if not _vazio(url) and not str(url).startswith(("http://", "https://")):
        ficha.erros.append("fonte_url precisa ser o endereço completo da página, começando com https://.")

    bruta = cabecalho.get("data_coleta")
    if not _vazio(bruta):
        data = _como_data(bruta)
        if data is None:
            ficha.erros.append("data_coleta precisa estar no formato AAAA-MM-DD (ex.: 2026-11-12).")
        elif data > hoje:
            ficha.erros.append("data_coleta está no futuro.")
        elif (hoje - data).days > IDADE_MAXIMA_DIAS:
            ficha.avisos.append(f"Coletada há mais de {IDADE_MAXIMA_DIAS} dias: confira se a página mudou.")

    for campo, valor in cabecalho.items():
        itens = valor if isinstance(valor, list) else [valor]
        if any(isinstance(item, str) and _PLACEHOLDER.search(item) for item in itens):
            ficha.erros.append(f"O campo {campo} ainda tem texto do modelo: troque pelo que está na fonte.")
    if _PLACEHOLDER.search(texto):
        ficha.erros.append("O texto ainda tem marcação do modelo (<…>, COLE AQUI ou substituir).")
    if len(texto) < TEXTO_MINIMO:
        ficha.erros.append(f"Texto muito curto ({len(texto)} caracteres; mínimo {TEXTO_MINIMO}). Cole o conteúdo da página.")

    for campo in ("orgao", "canal"):
        if _vazio(cabecalho.get(campo)):
            ficha.avisos.append(f"{campo} vazio: tudo bem se a fonte não informa.")

    return ficha


def ler_todas(pasta: Path, hoje: dt.date | None = None) -> list[Ficha]:
    fichas = [ler(arquivo, hoje) for arquivo in sorted(pasta.glob("*.md"))]

    # Mesma página copiada duas vezes deixa a busca enviesada
    vistas: dict[str, Path] = {}
    for ficha in fichas:
        url = str(ficha.cabecalho.get("fonte_url") or "").strip().rstrip("/")
        servico = str(ficha.cabecalho.get("servico") or "").strip().lower()
        if ficha.ignorada or not url:
            continue
        chave = f"{servico}|{url}"
        if chave in vistas:
            ficha.erros.append(f"Duplicada: mesmo serviço e mesma fonte de {vistas[chave].name}.")
        else:
            vistas[chave] = ficha.arquivo
    return fichas
