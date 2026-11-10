"""Testa a busca e a avaliação com fichas FICTÍCIAS e um embedder simples de palavras.

O embedder de teste conta palavras de um vocabulário pequeno: textos com as mesmas palavras
ficam parecidos. Assim dá para testar filtro, plano B e limiar sem baixar o modelo real.
"""

import math
import sys
import unicodedata
from pathlib import Path

import chromadb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from avaliar_busca import FIM, INICIO, avaliar, gravar_relatorio, relatorio  # noqa: E402
from indexar import indexar  # noqa: E402

from app.busca import Buscador  # noqa: E402

VOCABULARIO = ["buraco", "asfalto", "pneu", "poste", "lampada", "escuro", "bueiro", "entupido", "alaga",
               "chuva", "festa", "som"]


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def embedder_palavras(textos: list[str]) -> list[list[float]]:
    vetores = []
    for texto in textos:
        limpo = _sem_acento(texto)
        vetor = [float(limpo.count(p)) for p in VOCABULARIO] + [0.05]  # evita vetor zerado
        norma = math.sqrt(sum(v * v for v in vetor))
        vetores.append([v / norma for v in vetor])
    return vetores


ENCHIMENTO = " Texto fictício de teste, sem relação com serviços reais." * 4

FICHAS = {
    "tapa.md": ("Tapa fictício", "Buraco ou pavimento", "Conserto de buraco no asfalto que fura pneu."),
    "luz.md": ("Luz fictícia", "Iluminação pública", "Troca de lampada de poste quando a rua fica escuro."),
    "bueiro.md": ("Bueiro fictício", "Bueiro e drenagem", "Limpeza de bueiro entupido que alaga na chuva."),
}


def montar_base(tmp_path: Path):
    raw = tmp_path / "raw"
    raw.mkdir()
    for arquivo, (servico, categoria, texto) in FICHAS.items():
        (raw / arquivo).write_text(
            f"---\nservico: {servico}\ncategoria_rootfix: {categoria}\n"
            f"fonte_url: https://exemplo.invalid/{arquivo}\ndata_coleta: 2026-11-01\n---\n{texto}{ENCHIMENTO}\n",
            encoding="utf-8",
        )
    indexar(raw, tmp_path / "p", tmp_path / "v", embedder_palavras, nome_colecao="teste")
    return chromadb.PersistentClient(path=str(tmp_path / "v")).get_collection("teste")


def test_encontra_o_servico_certo(tmp_path):
    buscador = Buscador(embedder_palavras, montar_base(tmp_path), limiar=0.5)
    r = buscador.buscar("Poste apagado", "a rua fica escuro, a lampada queimou", "Iluminação pública")
    assert r.encontrado
    assert r.melhor.servico == "Luz fictícia"
    assert r.filtro_usado == "Iluminação pública" and not r.caiu_no_plano_b
    assert r.melhor.meta["fonte_url"] == "https://exemplo.invalid/luz.md"


def test_categoria_errada_cai_no_plano_b(tmp_path):
    buscador = Buscador(embedder_palavras, montar_base(tmp_path), limiar=0.5)
    r = buscador.buscar("Bueiro entupido", "quando tem chuva alaga tudo", "Buraco ou pavimento")
    assert r.caiu_no_plano_b
    assert r.filtro_usado is None
    assert r.melhor.servico == "Bueiro fictício"


def test_outros_e_sem_categoria_buscam_na_base_toda(tmp_path):
    buscador = Buscador(embedder_palavras, montar_base(tmp_path), limiar=0.5)
    for categoria in (None, "Outros", "Categoria inventada"):
        r = buscador.buscar("Buraco", "buraco no asfalto furou o pneu", categoria)
        assert r.filtro_usado is None and not r.caiu_no_plano_b
        assert r.melhor.servico == "Tapa fictício"


def test_problema_fora_do_catalogo_nao_e_encontrado(tmp_path):
    buscador = Buscador(embedder_palavras, montar_base(tmp_path), limiar=0.5)
    r = buscador.buscar("Vizinho", "festa com som alto toda noite", "Outros")
    assert not r.encontrado
    assert r.melhor.similaridade < 0.5  # há candidatos, mas fracos demais para confiar


def test_candidatos_agrupam_trechos_por_servico(tmp_path):
    buscador = Buscador(embedder_palavras, montar_base(tmp_path), limiar=0.5)
    r = buscador.buscar("Buraco", "buraco", None)
    servicos = [c.servico for c in r.candidatos]
    assert len(servicos) == len(set(servicos))


CASOS = [
    {"id": "t1", "tipo": "representativo", "titulo": "Buraco", "descricao": "buraco no asfalto furou pneu",
     "categoria_spring": "Buraco ou pavimento", "categoria_esperada": "Buraco ou pavimento",
     "servico_esperado": "Tapa fictício", "deveria_encontrar": True, "revisado": True},
    {"id": "t2", "tipo": "categoria_errada", "titulo": "Bueiro", "descricao": "bueiro entupido alaga na chuva",
     "categoria_spring": "Iluminação pública", "categoria_esperada": "Bueiro e drenagem",
     "servico_esperado": None, "deveria_encontrar": True, "revisado": False},
    {"id": "t3", "tipo": "fora_do_catalogo", "titulo": "Festa", "descricao": "festa com som alto",
     "categoria_spring": "Outros", "categoria_esperada": "Outros",
     "servico_esperado": None, "deveria_encontrar": False, "revisado": True},
]


def test_avaliacao_calcula_metricas_e_limiar(tmp_path):
    r = avaliar(CASOS, Buscador(embedder_palavras, montar_base(tmp_path), limiar=0.5))
    cf = r["com_filtro"]
    assert cf["casos_validos"] == 2 and cf["categoria_top1"] == 2
    assert cf["casos_com_servico"] == 1 and cf["servico_top1"] == 1 and cf["mrr"] == 1.0
    assert r["plano_b"] == {"casos_categoria_errada": 1, "acionado": 1, "categoria_certa_no_fim": 1}
    assert r["nao_revisados"] == 1
    assert len(r["varredura"]) == 11
    assert r["limiar_sugerido"] in [v["limiar"] for v in r["varredura"]]


def test_relatorio_substitui_so_a_secao_da_busca(tmp_path):
    r = avaliar(CASOS, Buscador(embedder_palavras, montar_base(tmp_path), limiar=0.5))
    arquivo = tmp_path / "avaliacao.md"
    arquivo.write_text("# Avaliação\n\nTexto escrito à mão.\n", encoding="utf-8")

    gravar_relatorio(relatorio(r), arquivo)
    gravar_relatorio(relatorio(r), arquivo)  # rodar duas vezes não duplica

    texto = arquivo.read_text(encoding="utf-8")
    assert texto.count(INICIO) == 1 and texto.count(FIM) == 1
    assert "Texto escrito à mão." in texto
    assert "provisórios" in texto  # avisa que há rótulo não revisado
