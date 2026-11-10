"""Transforma as fichas coletadas em uma base vetorial pronta para a busca.

    data/raw/*.md  →  data/processado/fichas.jsonl  →  data/vetores/ (Chroma)

Uso:  python scripts/indexar.py
Rodar de novo apaga a base e cria do zero, então é seguro depois de editar uma ficha.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app.config import config  # noqa: E402
from app.embeddings import Embedder  # noqa: E402
from app.fichas import ler_todas  # noqa: E402
from app.memoria import pico_mb  # noqa: E402
from app.preparacao import cabecalho_de_busca, dividir, limpar, metadados  # noqa: E402

LOTE = 32  # trechos por chamada ao modelo de embeddings


@dataclass
class Resumo:
    fichas_lidas: int = 0
    fichas_indexadas: int = 0
    puladas: list[str] = field(default_factory=list)
    com_erro: dict[str, list[str]] = field(default_factory=dict)
    trechos_por_categoria: Counter = field(default_factory=Counter)
    segundos: float = 0.0

    @property
    def total_trechos(self) -> int:
        return sum(self.trechos_por_categoria.values())


def indexar(pasta_raw: Path, pasta_processado: Path, pasta_vetores: Path, embedder: Embedder,
            nome_colecao: str = config.nome_colecao) -> Resumo:
    import chromadb

    inicio = time.perf_counter()
    resumo = Resumo()
    fichas = ler_todas(pasta_raw)
    resumo.fichas_lidas = len(fichas)

    ids: list[str] = []
    documentos: list[str] = []
    metas: list[dict] = []
    processadas: list[dict] = []

    for ficha in fichas:
        if ficha.ignorada:
            resumo.puladas.append(f"{ficha.arquivo.name} ({ficha.ignorada})")
            continue
        if ficha.erros:
            resumo.com_erro[ficha.arquivo.name] = ficha.erros
            continue

        texto = limpar(ficha.texto)
        meta = metadados(ficha)
        cabecalho = cabecalho_de_busca(ficha)
        trechos = dividir(texto)
        processadas.append({**meta, "texto": texto, "trechos": len(trechos)})

        for i, trecho in enumerate(trechos):
            ids.append(f"{ficha.arquivo.stem}#{i}")
            documentos.append(f"{cabecalho}\n{trecho}")
            metas.append({**meta, "trecho": i})
        resumo.fichas_indexadas += 1
        resumo.trechos_por_categoria[meta["categoria"]] += len(trechos)

    pasta_processado.mkdir(parents=True, exist_ok=True)
    with (pasta_processado / "fichas.jsonl").open("w", encoding="utf-8") as saida:
        for linha in processadas:
            saida.write(json.dumps(linha, ensure_ascii=False) + "\n")

    if not documentos:
        resumo.segundos = time.perf_counter() - inicio
        return resumo

    vetores: list[list[float]] = []
    for i in range(0, len(documentos), LOTE):
        vetores.extend(embedder(documentos[i : i + LOTE]))

    pasta_vetores.mkdir(parents=True, exist_ok=True)
    cliente = chromadb.PersistentClient(path=str(pasta_vetores))
    if nome_colecao in [c.name for c in cliente.list_collections()]:
        cliente.delete_collection(nome_colecao)
    colecao = cliente.create_collection(
        nome_colecao,
        metadata={"hnsw:space": "cosine"},  # similaridade de cosseno: 1 = mesmo sentido, 0 = nada a ver
        embedding_function=None,  # os vetores vêm prontos do nosso modelo
    )
    colecao.add(ids=ids, documents=documentos, embeddings=vetores, metadatas=metas)

    resumo.segundos = time.perf_counter() - inicio
    return resumo


def imprimir(resumo: Resumo) -> None:
    print(f"Fichas lidas: {resumo.fichas_lidas}  ·  indexadas: {resumo.fichas_indexadas}  ·  "
          f"puladas: {len(resumo.puladas)}  ·  com erro: {len(resumo.com_erro)}")
    for nome in resumo.puladas:
        print(f"  pulada   {nome}")
    for nome, erros in resumo.com_erro.items():
        print(f"  ERRO     {nome}: {erros[0]}" + (f" (+{len(erros) - 1})" if len(erros) > 1 else ""))
    if resumo.com_erro:
        print("  Rode python scripts/validar_fichas.py para ver todos os erros.")
    print()
    print(f"Trechos na base: {resumo.total_trechos}")
    for categoria, n in sorted(resumo.trechos_por_categoria.items()):
        print(f"  {categoria:<26} {n:>4}")
    print()
    print(f"Tempo: {resumo.segundos:.1f} s  ·  pico de memória: {pico_mb():.0f} MB")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--entrada", type=Path, default=RAIZ / "data" / "raw")
    parser.add_argument("--processado", type=Path, default=RAIZ / "data" / "processado")
    parser.add_argument("--vetores", type=Path, default=config.pasta_vetores)
    args = parser.parse_args()

    from app.embeddings import padrao

    def embedder(textos: list[str]) -> list[list[float]]:
        # O modelo só é carregado se houver fichas válidas (na primeira vez ele é baixado)
        if padrao.cache_info().currsize == 0:
            print(f"Carregando o modelo de embeddings {config.embeddings_modelo}…")
        return padrao()(textos)

    resumo = indexar(args.entrada, args.processado, args.vetores, embedder)
    imprimir(resumo)
    if resumo.fichas_indexadas == 0:
        print("\nNenhuma ficha válida: a base não foi criada. Colete as fichas em data/raw/ primeiro.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
