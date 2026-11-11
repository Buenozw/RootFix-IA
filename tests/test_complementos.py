"""Testes que fecham lacunas de cobertura: /health com base real, montagem da busca padrão,
formatos de data das fichas e medição de memória. Tudo com dados FICTÍCIOS."""

import dataclasses
import datetime as dt

import chromadb
import pytest
from fastapi.testclient import TestClient

import app.config as modulo_config
import app.main as principal
import app.servico as servico
from app.busca import BaseIncompativel, Buscador
from app.fichas import ler
from app.memoria import pico_mb

ASSINATURA = "gemini:gemini-embedding-001:768"


def criar_base(pasta, assinatura=ASSINATURA, itens=2):
    colecao = chromadb.PersistentClient(path=str(pasta)).create_collection(
        "fichas_156", metadata={"hnsw:space": "cosine", "embeddings": assinatura}, embedding_function=None)
    colecao.add(ids=[f"t{i}" for i in range(itens)], documents=["x"] * itens, embeddings=[[1.0, 0.0]] * itens,
                metadatas=[{"servico": "S", "categoria": "Outros", "arquivo": "a.md"}] * itens)
    return colecao


@pytest.fixture
def config_em(monkeypatch):
    """Aponta o serviço para uma pasta de vetores temporária."""
    def aplicar(pasta):
        nova = dataclasses.replace(modulo_config.config, pasta_vetores=pasta)
        monkeypatch.setattr(modulo_config, "config", nova)
        monkeypatch.setattr(principal, "config", nova)
        servico.buscador_padrao.cache_clear()
        return nova
    yield aplicar
    servico.buscador_padrao.cache_clear()


def test_health_com_base_compativel(tmp_path, config_em, monkeypatch):
    config_em(tmp_path)
    monkeypatch.setattr(principal, "assinatura", lambda: ASSINATURA)
    criar_base(tmp_path, itens=3)
    corpo = TestClient(principal.app).get("/health").json()
    assert corpo["trechosNaBase"] == 3 and corpo["baseIndexada"] and corpo["baseCompativel"]
    assert corpo["baseCriadaCom"] == ASSINATURA


def test_health_avisa_base_de_outro_modelo(tmp_path, config_em, monkeypatch):
    config_em(tmp_path)
    monkeypatch.setattr(principal, "assinatura", lambda: ASSINATURA)
    criar_base(tmp_path, assinatura="local:outro-modelo")
    corpo = TestClient(principal.app).get("/health").json()
    assert corpo["baseIndexada"] and not corpo["baseCompativel"]


def test_busca_padrao_sem_base_avisa_para_indexar(tmp_path, config_em):
    config_em(tmp_path)
    with pytest.raises(servico.BaseAusente):
        servico.buscador_padrao()


def test_busca_padrao_confere_o_modelo_da_base(tmp_path, config_em, monkeypatch):
    config_em(tmp_path)
    monkeypatch.setattr(servico, "para_consultas", lambda: (lambda textos: [[1.0, 0.0]] * len(textos)))
    criar_base(tmp_path, assinatura="local:outro-modelo")
    monkeypatch.setattr(servico, "assinatura", lambda: ASSINATURA)
    with pytest.raises(BaseIncompativel):
        servico.buscador_padrao()

    servico.buscador_padrao.cache_clear()
    monkeypatch.setattr(servico, "assinatura", lambda: "local:outro-modelo")
    assert isinstance(servico.buscador_padrao(), Buscador)


def test_busca_em_base_vazia_nao_encontra(tmp_path):
    colecao = chromadb.PersistentClient(path=str(tmp_path)).create_collection(
        "vazia", metadata={"hnsw:space": "cosine"}, embedding_function=None)
    r = Buscador(lambda t: [[1.0, 0.0]], colecao, limiar=0.5).buscar("Poste", "apagado", "Iluminação pública")
    assert not r.encontrado and r.candidatos == []


TEXTO = "Texto copiado da página oficial do serviço. " * 6


def ficha(tmp_path, cabecalho: str, nome="f.md"):
    arquivo = tmp_path / nome
    arquivo.write_text(f"---\n{cabecalho}\n---\n{TEXTO}", encoding="utf-8")
    return ler(arquivo, dt.date(2026, 11, 12))


BASE = "servico: S\ncategoria_rootfix: Outros\nfonte_url: https://exemplo.invalid\n"


def test_data_em_formato_brasileiro_e_erro(tmp_path):
    assert any("AAAA-MM-DD" in e for e in ficha(tmp_path, BASE + "data_coleta: 12/11/2026").erros)


def test_ficha_antiga_gera_aviso(tmp_path):
    f = ficha(tmp_path, BASE + "data_coleta: 2026-01-10")
    assert f.valida and any("60 dias" in a for a in f.avisos)


def test_campo_desconhecido_gera_aviso(tmp_path):
    f = ficha(tmp_path, BASE + "data_coleta: 2026-11-01\ntelefone: 156")
    assert f.valida and any("telefone" in a for a in f.avisos)


def test_arquivo_sem_cabecalho_e_erro(tmp_path):
    arquivo = tmp_path / "solto.md"
    arquivo.write_text(TEXTO, encoding="utf-8")
    assert any("cabeçalho" in e.lower() for e in ler(arquivo).erros)


def test_url_sem_https_e_erro(tmp_path):
    f = ficha(tmp_path, "servico: S\ncategoria_rootfix: Outros\nfonte_url: prefeitura.sp.gov.br\ndata_coleta: 2026-11-01")
    assert any("fonte_url" in e for e in f.erros)


def test_medicao_de_memoria_devolve_um_valor_positivo():
    assert pico_mb() > 0
