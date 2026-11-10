"""Confere o formato do conjunto de casos de teste (data/avaliacao/casos.jsonl)."""

import json
from collections import Counter
from pathlib import Path

from app.fichas import CATEGORIAS

ARQUIVO = Path(__file__).resolve().parent.parent / "data" / "avaliacao" / "casos.jsonl"
CAMPOS = {"id", "tipo", "titulo", "descricao", "categoria_spring", "categoria_esperada", "servico_esperado",
          "deveria_encontrar", "revisado", "nota"}
TIPOS = {"representativo", "informal", "fora_do_catalogo", "ambiguo", "categoria_errada", "desvio"}


def casos():
    return [json.loads(linha) for linha in ARQUIVO.read_text(encoding="utf-8").splitlines() if linha.strip()]


def test_tem_pelo_menos_30_casos_com_ids_unicos():
    lista = casos()
    assert len(lista) >= 30
    assert len({c["id"] for c in lista}) == len(lista)


def test_cada_caso_tem_os_campos_e_valores_validos():
    for caso in casos():
        assert set(caso) == CAMPOS, caso["id"]
        assert caso["tipo"] in TIPOS, caso["id"]
        assert caso["categoria_spring"] in CATEGORIAS, caso["id"]
        assert caso["categoria_esperada"] in CATEGORIAS or caso["categoria_esperada"] is None, caso["id"]
        assert isinstance(caso["deveria_encontrar"], bool), caso["id"]


def test_cobre_todos_os_tipos_e_todas_as_categorias():
    lista = casos()
    assert set(Counter(c["tipo"] for c in lista)) == TIPOS
    esperadas = {c["categoria_esperada"] for c in lista if c["deveria_encontrar"]}
    assert set(CATEGORIAS) <= esperadas


def test_categoria_errada_e_mesmo_errada():
    for caso in casos():
        if caso["tipo"] == "categoria_errada":
            assert caso["categoria_spring"] != caso["categoria_esperada"], caso["id"]
