"""Carrega o modelo de embeddings e mostra quanto de memória ele usa.

Uso:  python scripts/medir_memoria.py
O plano gratuito do Render tem 512 MB. O serviço inteiro (FastAPI + Chroma + modelo)
precisa ficar abaixo disso com folga.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import config  # noqa: E402
from app.memoria import pico_mb  # noqa: E402

LIMITE_RENDER_MB = 512


def main() -> int:
    antes = pico_mb()
    inicio = time.perf_counter()
    print(f"Carregando {config.embeddings_modelo} (na primeira vez ele é baixado, ~220 MB)…")

    import chromadb  # noqa: F401  (entra na conta porque o serviço também carrega o Chroma)

    from app.embeddings import padrao

    modelo = padrao()
    carregado = time.perf_counter()
    vetores = modelo(["poste apagado faz duas semanas", "buraco enorme na frente do mercado"])
    fim = time.perf_counter()

    total = pico_mb()
    print(f"Dimensão dos vetores: {len(vetores[0])}")
    print(f"Tempo para carregar: {carregado - inicio:.1f} s  ·  para gerar 2 vetores: {fim - carregado:.2f} s")
    print(f"Memória: {antes:.0f} MB antes  →  pico de {total:.0f} MB com o modelo e o Chroma")
    folga = LIMITE_RENDER_MB - total
    if folga < 100:
        print(f"ATENÇÃO: folga de só {folga:.0f} MB para o limite de {LIMITE_RENDER_MB} MB do Render.")
        return 1
    print(f"Folga de {folga:.0f} MB para o limite de {LIMITE_RENDER_MB} MB do Render.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
