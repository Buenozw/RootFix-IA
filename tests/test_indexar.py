"""Testa a indexação de ponta a ponta com fichas FICTÍCIAS e embeddings falsos.

As fichas daqui existem só no teste (pasta temporária), não vão para data/raw/ e não
representam serviços reais. O embedder falso evita baixar o modelo durante os testes.
"""

import hashlib
import json
import sys
from pathlib import Path

import chromadb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from indexar import indexar  # noqa: E402

TEXTO = "Texto fictício de teste, sem relação com serviços reais. " * 30


def embedder_falso(textos: list[str]) -> list[list[float]]:
    """Vetor de 8 posições derivado do texto: igual para textos iguais, diferente para diferentes."""
    vetores = []
    for texto in textos:
        bytes_ = hashlib.sha256(texto.encode()).digest()
        vetores.append([b / 255 for b in bytes_[:8]])
    return vetores


def ficha(nome: str, categoria: str, extra: str = "") -> str:
    return f"""---
servico: Serviço fictício {nome}
categoria_rootfix: {categoria}
fonte_url: https://exemplo.invalid/{nome}
data_coleta: 2026-11-01
termos_populares:
  - termo {nome}
{extra}---
{TEXTO}
"""


def preparar(tmp_path: Path) -> tuple[Path, Path, Path]:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "a.md").write_text(ficha("a", "Buraco ou pavimento"), encoding="utf-8")
    (raw / "b.md").write_text(ficha("b", "Iluminação pública"), encoding="utf-8")
    (raw / "ruim.md").write_text(ficha("ruim", "Categoria que não existe"), encoding="utf-8")
    (raw / "_MODELO.md").write_text(ficha("modelo", "Outros"), encoding="utf-8")
    return raw, tmp_path / "processado", tmp_path / "vetores"


def test_indexa_so_as_fichas_validas(tmp_path):
    raw, processado, vetores = preparar(tmp_path)
    resumo = indexar(raw, processado, vetores, embedder_falso, nome_colecao="teste")

    assert resumo.fichas_lidas == 4
    assert resumo.fichas_indexadas == 2
    assert "ruim.md" in resumo.com_erro
    assert any("_MODELO.md" in p for p in resumo.puladas)
    assert set(resumo.trechos_por_categoria) == {"Buraco ou pavimento", "Iluminação pública"}

    colecao = chromadb.PersistentClient(path=str(vetores)).get_collection("teste")
    assert colecao.count() == resumo.total_trechos


def test_trecho_guarda_metadados_e_cabecalho_de_busca(tmp_path):
    raw, processado, vetores = preparar(tmp_path)
    indexar(raw, processado, vetores, embedder_falso, nome_colecao="teste")

    colecao = chromadb.PersistentClient(path=str(vetores)).get_collection("teste")
    item = colecao.get(where={"categoria": "Iluminação pública"}, limit=1)
    meta, documento = item["metadatas"][0], item["documents"][0]
    assert meta["servico"] == "Serviço fictício b"
    assert meta["fonte_url"] == "https://exemplo.invalid/b"
    assert documento.startswith("Serviço: Serviço fictício b. Categoria: Iluminação pública. Também chamado de: termo b.")


def test_gera_o_jsonl_processado(tmp_path):
    raw, processado, vetores = preparar(tmp_path)
    indexar(raw, processado, vetores, embedder_falso, nome_colecao="teste")

    linhas = (processado / "fichas.jsonl").read_text(encoding="utf-8").splitlines()
    servicos = {json.loads(linha)["servico"] for linha in linhas}
    assert servicos == {"Serviço fictício a", "Serviço fictício b"}


def test_rodar_de_novo_recria_a_base(tmp_path):
    raw, processado, vetores = preparar(tmp_path)
    primeira = indexar(raw, processado, vetores, embedder_falso, nome_colecao="teste")
    (raw / "b.md").unlink()
    segunda = indexar(raw, processado, vetores, embedder_falso, nome_colecao="teste")

    colecao = chromadb.PersistentClient(path=str(vetores)).get_collection("teste")
    assert colecao.count() == segunda.total_trechos < primeira.total_trechos


def test_sem_fichas_validas_nao_cria_base(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    resumo = indexar(raw, tmp_path / "p", tmp_path / "v", embedder_falso, nome_colecao="teste")
    assert resumo.fichas_indexadas == 0
    assert not (tmp_path / "v").exists()
