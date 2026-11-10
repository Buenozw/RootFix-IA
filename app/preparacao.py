"""Limpeza e divisão em trechos das fichas, antes de gerar os embeddings."""

from __future__ import annotations

import re
import unicodedata

from app.fichas import Ficha

TAMANHO_TRECHO = 800  # caracteres; cabe com folga no limite do modelo de embeddings
SOBREPOSICAO = 150  # caracteres repetidos entre trechos vizinhos, para não cortar uma ideia no meio

# Linhas que costumam vir junto quando se copia uma página do portal da prefeitura
_LIXO_DE_PAGINA = re.compile(
    r"^(compartilhar|imprimir|voltar( ao topo)?|ir para o conteúdo|ir para o menu|acessibilidade|"
    r"alto contraste|mapa do site|facebook|twitter|x|instagram|youtube|linkedin|whatsapp|"
    r"copiar link|enviar por e-?mail|última atualização.*|publicado em.*|atualizado em.*|"
    r"início|home|menu|buscar|pesquisar|fechar)\s*[:|]?\s*$",
    re.IGNORECASE,
)


def limpar(texto: str) -> str:
    """Tira sobras de página, espaços repetidos e linhas duplicadas, mantendo a ordem."""
    texto = unicodedata.normalize("NFC", texto).replace(" ", " ")
    linhas_limpas: list[str] = []
    vistas: set[str] = set()
    for linha in texto.splitlines():
        linha = re.sub(r"[ \t]+", " ", linha).strip()
        if not linha:
            if linhas_limpas and linhas_limpas[-1] != "":
                linhas_limpas.append("")  # mantém a separação de parágrafos
            continue
        if _LIXO_DE_PAGINA.match(linha):
            continue
        chave = linha.lower()
        if chave in vistas and len(linha) > 20:
            continue  # parágrafo copiado duas vezes
        vistas.add(chave)
        linhas_limpas.append(linha)
    return "\n".join(linhas_limpas).strip()


def _frases(paragrafo: str) -> list[str]:
    return [f for f in re.split(r"(?<=[.!?;:])\s+", paragrafo) if f]


def dividir(texto: str, tamanho: int = TAMANHO_TRECHO, sobreposicao: int = SOBREPOSICAO) -> list[str]:
    """Junta frases até perto do tamanho e começa o trecho seguinte repetindo o final do anterior."""
    unidades: list[str] = []
    for paragrafo in texto.split("\n\n"):
        paragrafo = paragrafo.replace("\n", " ").strip()
        if not paragrafo:
            continue
        for frase in _frases(paragrafo):
            # frase gigante (lista sem pontuação, por exemplo) é cortada à força
            while len(frase) > tamanho:
                unidades.append(frase[:tamanho])
                frase = frase[tamanho - sobreposicao :]
            unidades.append(frase)

    trechos: list[str] = []
    atual: list[str] = []
    for unidade in unidades:
        if atual and len(" ".join(atual + [unidade])) > tamanho:
            trechos.append(" ".join(atual))
            # sobreposição: leva as últimas frases do trecho anterior
            reaproveitar: list[str] = []
            for frase in reversed(atual):
                if len(" ".join([frase] + reaproveitar)) > sobreposicao:
                    break
                reaproveitar.insert(0, frase)
            atual = reaproveitar
        atual.append(unidade)
    if atual:
        trechos.append(" ".join(atual))
    return trechos


def _texto_de(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, list):
        return "; ".join(str(v) for v in valor if v)
    return str(valor).strip()


def cabecalho_de_busca(ficha: Ficha) -> str:
    """Linha colocada no início de cada trecho para a busca saber de que serviço ele fala.

    Sem isso, um trecho do meio da ficha ("informe o endereço e uma foto") não diz se é de
    tapa-buraco ou de poda, e qualquer problema o encontraria.
    """
    c = ficha.cabecalho
    partes = [f"Serviço: {_texto_de(c.get('servico'))}.", f"Categoria: {_texto_de(c.get('categoria_rootfix'))}."]
    termos = _texto_de(c.get("termos_populares"))
    if termos:
        partes.append(f"Também chamado de: {termos}.")
    return " ".join(partes)


def metadados(ficha: Ficha) -> dict[str, str]:
    """Metadados guardados com cada trecho. O Chroma só aceita valores simples (texto, número)."""
    c = ficha.cabecalho
    return {
        "arquivo": ficha.arquivo.name,
        "servico": _texto_de(c.get("servico")),
        "categoria": _texto_de(c.get("categoria_rootfix")),
        "orgao": _texto_de(c.get("orgao")),
        "subprefeitura": _texto_de(c.get("subprefeitura")),
        "canal": _texto_de(c.get("canal")),
        "prazo_referencia": _texto_de(c.get("prazo_referencia")),
        "documentos_necessarios": _texto_de(c.get("documentos_necessarios")),
        "fonte_url": _texto_de(c.get("fonte_url")),
        "data_coleta": _texto_de(c.get("data_coleta")),
    }
