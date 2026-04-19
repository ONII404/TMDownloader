# /utils/BatchManager.py
"""
Lee una lista de URLs desde lista.txt en la raíz del proyecto.
Cada manga se descarga completamente antes de pasar al siguiente,
con una pausa configurable entre descargas para evitar baneos.
"""
import time
from pathlib import Path
from utils.ui import _c

# Ruta fija: lista.txt en la raíz del proyecto (un nivel arriba de /utils/)
BATCH_FILE = Path(__file__).parent.parent / "lista.txt"

# Pausa en segundos entre la descarga de un manga y el siguiente
DELAY_BETWEEN_DOWNLOADS = 5

_TEMPLATE = """\
# TMD - Lista de descargas en lote
# Una URL por línea. Las líneas que empiezan con # son comentarios.
# Puedes usar URLs completas o IDs de 13 caracteres.
#
# Ejemplos:
# https://tmohentai.com/contents/69b6fd0b4a6fa
# https://lectorhentai.com/manga/90184/hamegaki-x-yaritsuma
"""


def ensure_batch_file() -> bool:
    """
    Verifica que lista.txt exista en la raíz del proyecto.
    Si no existe, lo crea con la plantilla y retorna False.
    Si existe, retorna True.
    """
    if BATCH_FILE.exists():
        return True

    BATCH_FILE.write_text(_TEMPLATE, encoding="utf-8")
    print(_c("93;1", f"\n  [!] No existía lista.txt — se creó la plantilla en:"))
    print(_c("90",   f"      {BATCH_FILE}"))
    print(_c("90",    "      Añade tus URLs y vuelve a elegir esta opción.\n"))
    return False


def load_urls() -> list[str]:
    """
    Lee lista.txt y retorna las URLs válidas.
    - Ignora líneas vacías y comentarios (# al inicio)
    - Elimina duplicados manteniendo el orden
    """
    seen = set()
    urls = []
    with open(BATCH_FILE, encoding="utf-8") as f:
        for line in f:
            url = line.strip()
            if not url or url.startswith("#"):
                continue
            if url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


def run_batch(
    urls: list[str],
    download_fn,
    output_path: str,
    conv_format: str | None,
    cookies: str | None,
    delay: int = DELAY_BETWEEN_DOWNLOADS,
) -> dict:
    """
    Ejecuta download_fn para cada URL de la lista secuencialmente.
    Espera `delay` segundos entre descargas (excepto tras la última).
    Retorna dict con listas 'ok' y 'failed'.
    """
    total  = len(urls)
    ok     = []
    failed = []
    sep    = "─" * 50

    print(_c("97;1", f"\n  DESCARGA EN LOTE — {total} manga(s)\n"))

    for i, url in enumerate(urls, 1):
        print(_c("90",   f"  {sep}"))
        print(_c("96;1", f"  [{i}/{total}] {url}"))

        try:
            success = download_fn(url, output_path, conv_format, cookies)
            (ok if success else failed).append(url)
        except Exception as e:
            print(_c("91;1", f"  [!] Error inesperado: {e}"))
            failed.append(url)

        # Pausa entre descargas (no después de la última)
        if i < total and delay > 0:
            print(_c("90", f"\n  ⏳ Esperando {delay}s antes de la siguiente descarga..."))
            time.sleep(delay)

    # Resumen final
    print(_c("90",   f"\n  {sep}"))
    print(_c("97;1",  "  RESUMEN DEL LOTE"))
    print(_c("92;1",  f"  ✓ Completados : {len(ok)}"))
    if failed:
        print(_c("91;1", f"  ✗ Fallidos    : {len(failed)}"))
        for u in failed:
            print(_c("91", f"    - {u}"))
    print(_c("90", f"  {sep}\n"))

    return {"ok": ok, "failed": failed}