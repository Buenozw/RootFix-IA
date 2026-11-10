"""Mede o pico de memória do processo, para saber se o serviço cabe no plano gratuito do Render."""

import psutil


def pico_mb() -> float:
    info = psutil.Process().memory_info()
    # Windows informa o pico direto; Linux e macOS só o uso atual por aqui
    pico = getattr(info, "peak_wset", None)
    if pico is None:
        try:
            import resource
            import sys

            maximo = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            pico = maximo if sys.platform == "darwin" else maximo * 1024  # macOS em bytes, Linux em KB
        except ImportError:
            pico = info.rss
    return pico / (1024 * 1024)
