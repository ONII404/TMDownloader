# main.py
import sys
import argparse

from core.Session import SessionManager
from core.DownloadEngine import DownloadEngine
from core.ScraperFactory import ScraperFactory
from utils.FileManager import FileManager
from utils.history import HistoryManager
from utils.config import get_output_path, save_config
from utils.ui import ui_banner, _c, _cls, _pause, _ask


def _ask_output_path() -> str:
    """Pregunta la ruta de salida mostrando la última usada como default."""
    last = get_output_path()
    print(_c("90", f"  Ruta de salida [{last}]"))
    val = _ask(_c("93;1", "  Ruta (Enter para usar la de arriba) > "))
    path = val if val else last
    save_config({"last_output": path})
    return path


def _ask_conv_format() -> str | None:
    """Pregunta si convertir imágenes y a qué formato."""
    print()
    print(_c("97;1", "  Formato de imágenes:"))
    print("  [1] Mantener originales (webp/jpg/png)")
    print("  [2] Convertir a JPG")
    print("  [3] Convertir a AVIF  (requiere Pillow + libavif)")
    op = _ask(_c("93;1", "  Opción > "))
    return {"2": "jpg", "3": "avif"}.get(op, None)


def process_download(url: str, output_path: str, conv_format: str | None, cookies: str | None):
    # 1 ── Identificar scraper
    scraper = ScraperFactory.get_scraper(url)
    if not scraper:
        print(_c("91;1", f"\n[!] No hay soporte para esta URL: {url}"))
        return

    # 2 ── Sesión y Engine
    sm     = SessionManager(cookies_file=cookies)
    engine = DownloadEngine(sm.get_session(), max_workers=8)
    session = sm.get_session()

    # 3 ── ID y carpeta de destino
    cid      = scraper.extract_id(url)
    dest_dir = FileManager.prepare_dir(output_path, cid)

    print(_c("96;1", f"\n[*] Iniciando descarga: {cid}"))
    print(_c("90",   f"  Carpeta temporal : {dest_dir}"))

    # 4 ── Metadata (antes del probing para no hacer dos requests)
    print(_c("93;1", "  Obteniendo metadata..."))
    meta = scraper.get_metadata(session, cid)
    print(_c("90",   f"  Título           : {meta.get('Title', '?')}"))

    # 5 ── Probing de imágenes
    print(_c("93;1", "  Buscando imágenes en el CDN..."))
    tasks = scraper.get_image_tasks(session, cid, dest_dir)

    if not tasks:
        print(_c("91;1", "[!] No se encontraron imágenes o el sitio bloqueó la petición."))
        return

    print(_c("97;1", f"  {len(tasks)} imágenes encontradas. Descargando en paralelo...\n"))

    # 6 ── Descarga paralela
    success = engine.download_manga(tasks)

    # 7 ── Post-procesamiento
    if success:
        cbz_file = FileManager.compress_and_clean(dest_dir, meta=meta, conv_format=conv_format)
        HistoryManager().add(url)
        print(_c("92;1", f"\n[OK] ¡Éxito! Archivo guardado en: {cbz_file}"))
    else:
        print(_c("93;1", "\n[!] Descarga incompleta. Se conservaron los archivos temporales."))
        print(_c("90",   f"    Revisa los archivos en: {dest_dir}"))


def main():
    parser = argparse.ArgumentParser(description="Multi-Site Hentai Downloader")
    parser.add_argument("url",       nargs="?",  help="URL del manga")
    parser.add_argument("--output",  "-o",       help="Ruta de salida")
    parser.add_argument("--cookies", "-c",       help="Archivo de cookies")
    parser.add_argument("--format",  "-f",       choices=["jpg", "avif"],
                        help="Convertir imágenes a este formato")
    args = parser.parse_args()

    # ── Modo no-interactivo (URL por argumento) ──────────────────────────────
    if args.url:
        output = args.output or get_output_path()
        process_download(args.url, output, args.format, args.cookies)
        return

    # ── Modo interactivo ─────────────────────────────────────────────────────
    history = HistoryManager()

    while True:
        _cls()
        ui_banner()
        print(_c("97;1", "  MENU PRINCIPAL"))
        print("  [1] Descargar manga")
        print("  [2] Ver historial")
        print("  [3] Salir")

        op = _ask(_c("93;1", "\n  Opcion > "))

        if op == "1":
            _cls()
            ui_banner()
            print(_c("97;1", "  DESCARGAR MANGA\n"))

            url = _ask(_c("96;1", "  URL / ID > "))
            if not url:
                continue

            output     = _ask_output_path()
            conv_fmt   = _ask_conv_format()
            cookies    = None   # en interactivo no pedimos cookies (se puede extender)

            process_download(url, output, conv_fmt, cookies)
            _pause()

        elif op == "2":
            _cls()
            ui_banner()
            print(_c("97;1", "  HISTORIAL (últimas 50 descargas)\n"))
            entries = history.get_last(50)
            if entries:
                for e in entries:
                    print(_c("90", f"  {e}"))
            else:
                print(_c("90", "  No hay descargas registradas aún."))
            _pause()

        elif op == "3":
            break


if __name__ == "__main__":
    main()