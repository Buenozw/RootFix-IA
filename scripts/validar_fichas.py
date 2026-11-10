"""Confere as fichas de data/raw/ e mostra quanto falta coletar por categoria.

Uso:  python scripts/validar_fichas.py
Sai com código 1 se alguma ficha tiver erro, para dar para usar antes do commit.
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.fichas import CATEGORIAS, ler_todas  # noqa: E402

PASTA = Path(__file__).resolve().parent.parent / "data" / "raw"
META_POR_CATEGORIA = 3
META_TOTAL = (30, 50)


def main() -> int:
    fichas = ler_todas(PASTA)
    validas = [f for f in fichas if f.valida]
    com_erro = [f for f in fichas if f.erros]
    ignoradas = [f for f in fichas if f.ignorada]

    for ficha in fichas:
        if ficha.ignorada:
            print(f"  pulada   {ficha.arquivo.name}  ({ficha.ignorada})")
        elif ficha.erros:
            print(f"  ERRO     {ficha.arquivo.name}")
            for erro in ficha.erros:
                print(f"             - {erro}")
        else:
            print(f"  ok       {ficha.arquivo.name}")
        for aviso in ficha.avisos:
            print(f"             aviso: {aviso}")

    print()
    print(f"Fichas válidas: {len(validas)}  ·  com erro: {len(com_erro)}  ·  puladas: {len(ignoradas)}")
    print(f"Meta: {META_TOTAL[0]} a {META_TOTAL[1]} fichas, pelo menos {META_POR_CATEGORIA} por categoria.")
    print()

    contagem = Counter(f.categoria for f in validas)
    largura = max(len(c) for c in CATEGORIAS)
    for categoria in CATEGORIAS:
        n = contagem.get(categoria, 0)
        falta = max(0, META_POR_CATEGORIA - n)
        marca = "ok" if falta == 0 else f"faltam {falta}"
        print(f"  {categoria.ljust(largura)}  {n:>3}  {marca}")

    return 1 if com_erro else 0


if __name__ == "__main__":
    sys.exit(main())
