"""Prepara o provedor de embeddings e o Chroma e mostra quanto de memória o serviço usa.

Uso:  python scripts/medir_memoria.py
O plano gratuito do Render tem 512 MB. O serviço inteiro precisa ficar abaixo disso com folga.

Com EMBEDDINGS_PROVEDOR=gemini, gera 2 vetores pela API (gasta 2 chamadas da cota).
Com EMBEDDINGS_PROVEDOR=local, carrega o modelo local (na primeira vez ele é baixado, ~220 MB).
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

    import chromadb  # noqa: F401  (entra na conta porque o serviço também carrega o Chroma)

    from app.embeddings import EmbeddingsIndisponiveis, assinatura, para_consultas

    print(f"Preparando {assinatura()}…")
    try:
        modelo = para_consultas()
        carregado = time.perf_counter()
        vetores = modelo(["poste apagado faz duas semanas", "buraco enorme na frente do mercado"])
    except EmbeddingsIndisponiveis as erro:
        print(f"Não foi possível gerar embeddings: {erro}")
        return 1
    fim = time.perf_counter()

    total = pico_mb()
    print(f"Dimensão dos vetores: {len(vetores[0])}")
    print(f"Tempo para preparar: {carregado - inicio:.1f} s  ·  para gerar 2 vetores: {fim - carregado:.2f} s")
    print(f"Memória: {antes:.0f} MB antes  →  pico de {total:.0f} MB com os embeddings e o Chroma")
    folga = LIMITE_RENDER_MB - total
    if folga < 100:
        print(f"ATENÇÃO: folga de só {folga:.0f} MB para o limite de {LIMITE_RENDER_MB} MB do Render.")
        return 1
    print(f"Folga de {folga:.0f} MB para o limite de {LIMITE_RENDER_MB} MB do Render.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
