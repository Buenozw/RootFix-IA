"""Reindexar com o servidor no ar não pode quebrar o encaminhamento."""

import subprocess
import sys

import chromadb

import app.servico as servico
from app.busca import Buscador
from app.modelos import Encaminhamento, ProblemaAnonimo

PROBLEMA = ProblemaAnonimo(titulo="Poste apagado", descricao="rua escura")


class GeradorFalso:
    def encaminhar(self, problema, busca):
        return Encaminhamento(encontrado=busca.encontrado, servico=busca.melhor.servico if busca.melhor else None,
                              aviso="a")


def criar_base(pasta, servico_nome: str) -> None:
    """Cria a base em OUTRO processo, como o scripts/indexar.py faz."""
    codigo = f"""
import chromadb
c = chromadb.PersistentClient(path={str(pasta)!r})
if "fichas_156" in [x.name for x in c.list_collections()]:
    c.delete_collection("fichas_156")
col = c.create_collection("fichas_156", metadata={{"hnsw:space": "cosine"}}, embedding_function=None)
col.add(ids=["a"], documents=["Serviço: {servico_nome}.\\ntexto"], embeddings=[[1.0, 0.0]],
        metadatas=[{{"servico": {servico_nome!r}, "categoria": "Iluminação pública", "arquivo": "a.md"}}])
"""
    subprocess.run([sys.executable, "-c", codigo], check=True)


def test_reindexar_com_o_servidor_no_ar_recarrega_a_base(tmp_path, monkeypatch):
    def buscador_de_teste():
        colecao = chromadb.PersistentClient(path=str(tmp_path)).get_collection("fichas_156")
        return Buscador(lambda textos: [[1.0, 0.0]], colecao, limiar=0.5)

    cache = servico.lru_cache(maxsize=1)(buscador_de_teste)
    monkeypatch.setattr(servico, "buscador_padrao", cache)

    criar_base(tmp_path, "Luz antiga")
    assert servico.encaminhar(PROBLEMA, gerador=GeradorFalso()).servico == "Luz antiga"

    criar_base(tmp_path, "Luz nova")  # reindexação enquanto o serviço está no ar
    assert servico.encaminhar(PROBLEMA, gerador=GeradorFalso()).servico == "Luz nova"
