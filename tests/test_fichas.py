import datetime as dt
from pathlib import Path

from app.fichas import ler, ler_todas

HOJE = dt.date(2026, 11, 12)
TEXTO = "Texto copiado da página oficial do serviço. " * 6

VALIDA = f"""---
servico: Tapa-buraco
categoria_rootfix: Buraco ou pavimento
fonte_url: https://prefeitura.sp.gov.br/servico
data_coleta: 2026-11-11
orgao: Subprefeitura
canal: SP156
---
{TEXTO}
"""


def escrever(pasta: Path, nome: str, conteudo: str) -> Path:
    arquivo = pasta / nome
    arquivo.write_text(conteudo, encoding="utf-8")
    return arquivo


def test_ficha_completa_e_valida(tmp_path):
    ficha = ler(escrever(tmp_path, "ok.md", VALIDA), HOJE)
    assert ficha.valida, ficha.erros
    assert ficha.categoria == "Buraco ou pavimento"


def test_modelo_e_exemplo_sao_pulados(tmp_path):
    assert ler(escrever(tmp_path, "_MODELO.md", VALIDA), HOJE).ignorada
    exemplo = VALIDA.replace("servico:", "exemplo: true\nservico:")
    assert ler(escrever(tmp_path, "ex.md", exemplo), HOJE).ignorada


def test_categoria_inexistente_e_erro(tmp_path):
    conteudo = VALIDA.replace("Buraco ou pavimento", "Buracos")
    assert any("categoria_rootfix" in e for e in ler(escrever(tmp_path, "c.md", conteudo), HOJE).erros)


def test_campo_obrigatorio_vazio_e_erro(tmp_path):
    conteudo = VALIDA.replace("fonte_url: https://prefeitura.sp.gov.br/servico", "fonte_url:")
    assert any("fonte_url" in e for e in ler(escrever(tmp_path, "u.md", conteudo), HOJE).erros)


def test_texto_do_modelo_esquecido_e_erro(tmp_path):
    conteudo = VALIDA.replace("orgao: Subprefeitura", "orgao: <órgão responsável>")
    assert any("orgao" in e for e in ler(escrever(tmp_path, "m.md", conteudo), HOJE).erros)


def test_data_no_futuro_e_erro(tmp_path):
    conteudo = VALIDA.replace("2026-11-11", "2026-12-01")
    assert any("futuro" in e for e in ler(escrever(tmp_path, "d.md", conteudo), HOJE).erros)


def test_texto_curto_e_erro(tmp_path):
    conteudo = VALIDA.replace(TEXTO, "curto")
    assert any("curto" in e for e in ler(escrever(tmp_path, "t.md", conteudo), HOJE).erros)


def test_cabecalho_quebrado_vira_erro_e_nao_excecao(tmp_path):
    ficha = ler(escrever(tmp_path, "y.md", "---\nservico: [sem fechar\n---\ntexto"), HOJE)
    assert ficha.erros and not ficha.valida


def test_duplicada_e_apontada(tmp_path):
    escrever(tmp_path, "a.md", VALIDA)
    escrever(tmp_path, "b.md", VALIDA)
    fichas = ler_todas(tmp_path, HOJE)
    assert sum(1 for f in fichas if any("Duplicada" in e for e in f.erros)) == 1
