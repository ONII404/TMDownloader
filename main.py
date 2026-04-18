# main.py
import sys
import subprocess

# ── Auto-instalación de dependencias ────────────────────────────────────────
_REQUIRED = ["requests", "cloudscraper"]

def _ensure_deps():
    missing = []
    for pkg in _REQUIRED:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"[setup] Instalando dependencias: {', '.join(missing)}")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet",
             "--break-system-packages", *missing],
            stderr=subprocess.DEVNULL,
        )
        print("[setup] Dependencias instaladas. Continuando...\n")

_ensure_deps()

# ── Imports normales ─────────────────────────────────────────────────────────
import argparse

from core.Session import SessionManager
from core.DownloadEngine import DownloadEngine
from core.ScraperFactory import ScraperFactory
from utils.FileManager import FileManager
from utils.history import HistoryManager
from utils.config import get_output_path, save_config
from utils.ui import ui_banner, _c, _cls, _pause, _ask


# ── Helpers de UI ─────────────────────────────────────────────────────────────

def _ask_output_path() -> str:
    last = get_output_path()
    print(_c("90", f"  Ruta de salida [{last}]"))
    val = _ask(_c("93;1", "  Ruta (Enter para usar la de arriba) > "))
    path = val if val else last
    save_config({"last_output": path})
    return path


def _ask_conv_format() -> str | None:
    print()
    print(_c("97;1", "  Formato de imágenes:"))
    print("  [1] Mantener originales (webp/jpg/png)")
    print("  [2] Convertir a JPG")
    print("  [3] Convertir a AVIF  (requiere Pillow + libavif)")
    op = _ask(_c("93;1", "  Opción > "))
    return {"2": "jpg", "3": "avif"}.get(op, None)


def _print_download_header(index: int, total: int, meta: dict, cid: str) -> None:
    """
    Imprime el encabezado visual de una descarga individual.

    Ejemplo:
    ══════════════════════════════════════════════════
      Descarga  [1 / 3]
      Serie   : Loca por Ti
      Título  : Loca por Ti
      Fuente  : LectorHentai
    ══════════════════════════════════════════════════
    """
    sep   = "═" * 50
    title  = meta.get("Title",  cid)
    series = meta.get("Series", "")
    source = meta.get("Source", "")
    chapter = meta.get("Number", "")

    print()
    print(_c("96", f"  {sep}"))

    if total > 1:
        print(_c("97;1", f"  Descarga  [{index} / {total}]"))
    else:
        print(_c("97;1",  "  Descarga"))

    if series and series != title:
        print(_c("97",   f"  Serie   : ") + _c("93;1", series))
        print(_c("97",   f"  Título  : ") + _c("93;1", title))
    else:
        print(_c("97",   f"  Título  : ") + _c("93;1", title))

    if chapter and chapter != "1":
        print(_c("97",   f"  Capítulo: ") + _c("90",   chapter))

    if source:
        print(_c("97",   f"  Fuente  : ") + _c("90",   source))

    print(_c("96", f"  {sep}"))


# ── Lógica principal de descarga ──────────────────────────────────────────────

def process_download(
    url: str,
    output_path: str,
    conv_format: str | None,
    cookies: str | None,
    batch_index: int = 1,
    batch_total: int = 1,
) -> bool:
    """
    Descarga un manga/capítulo desde `url`.

    batch_index / batch_total : posición dentro de un lote (para el header).
    """
    scraper = ScraperFactory.get_scraper(url)
    if not scraper:
        print(_c("91;1", f"\n  [!] No hay soporte para esta URL: {url}"))
        return False

    sm      = SessionManager(cookies_file=cookies)
    session = sm.get_session()
    engine  = DownloadEngine(session, max_workers=8)

    # ── IDs y rutas ──────────────────────────────────────────────────────────
    cid      = scraper.extract_id(url)
    dest_dir = FileManager.prepare_dir(output_path, cid)

    # ── Metadata (antes del header para mostrar el título real) ──────────────
    print(_c("90", "\n  Obteniendo metadata..."), end="", flush=True)
    meta = scraper.get_metadata(session, cid)
    print(_c("92", " ✓"))

    _print_download_header(batch_index, batch_total, meta, cid)

    # ── Búsqueda de imágenes ─────────────────────────────────────────────────
    print(_c("90", "  Buscando imágenes..."), end="", flush=True)
    tasks = scraper.get_image_tasks(session, cid, dest_dir)

    if not tasks:
        print(_c("91;1", " ✗"))
        print(_c("91;1", "  [!] No se encontraron imágenes o el sitio bloqueó la petición."))
        return False

    print(_c("92", f" ✓  ({len(tasks)} imágenes)"))
    print()

    # ── Descarga ─────────────────────────────────────────────────────────────
    title_display = meta.get("Title", cid)
    success = engine.download_manga(tasks, title=title_display)

    # ── Empaquetado ──────────────────────────────────────────────────────────
    if success:
        # series_name para subcarpeta: usa meta["Series"] si existe,
        # si no el nombre del cid (oneshot → misma carpeta que cbz)
        series_name = meta.get("Series") or None

        cbz_file = FileManager.compress_and_clean(
            dest_dir,
            meta=meta,
            conv_format=conv_format,
            series_name=series_name,
        )
        HistoryManager().add(url)
        print(_c("92;1", f"\n  ✓  Guardado en: {cbz_file}"))
    else:
        print(_c("93;1", "\n  ⚠  Descarga incompleta — archivos conservados en:"))
        print(_c("90",   f"     {dest_dir}"))

    return success


# ── Wrapper para BatchManager (firma fija: url, output, fmt, cookies) ─────────

def _batch_download_wrapper(
    url: str,
    output_path: str,
    conv_format: str | None,
    cookies: str | None,
    # Estos dos los inyecta run_batch a través de un closure en cada iteración
    index: int = 1,
    total: int = 1,
) -> bool:
    return process_download(url, output_path, conv_format, cookies, index, total)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="TMD Manga Downloader")
    parser.add_argument("url",       nargs="?",              help="URL de un manga")
    parser.add_argument("--batch",   "-b", action="store_true",
                        help="Modo lote (lee lista.txt)")
    parser.add_argument("--output",  "-o",                   help="Ruta de salida")
    parser.add_argument("--cookies", "-c",                   help="Archivo de cookies")
    parser.add_argument("--format",  "-f", choices=["jpg", "avif"],
                        help="Convertir imágenes a este formato")
    args = parser.parse_args()

    output = args.output or get_output_path()

    # ── Modo no-interactivo: URL única ───────────────────────────────────────
    if args.url:
        process_download(args.url, output, args.format, args.cookies)
        return

    # ── Modo no-interactivo: lote desde CLI ──────────────────────────────────
    if args.batch:
        from utils.BatchManager import ensure_batch_file, load_urls, run_batch
        if not ensure_batch_file():
            return
        urls = load_urls()
        if not urls:
            print(_c("93;1", "[!] lista.txt no contiene URLs válidas."))
            return

        total = len(urls)

        def _fn(url, out, fmt, cook):
            idx = urls.index(url) + 1
            return process_download(url, out, fmt, cook, idx, total)

        run_batch(urls, _fn, output, args.format, args.cookies)
        return

    # ── Modo interactivo ─────────────────────────────────────────────────────
    history = HistoryManager()

    while True:
        _cls()
        ui_banner()
        print(_c("97;1", "  MENU PRINCIPAL"))
        print("  [1] Descargar manga")
        print("  [2] Descarga en lote  (.txt)")
        print("  [3] Ver historial")
        print("  [4] Salir")

        op = _ask(_c("93;1", "\n  Opcion > "))

        if op == "1":
            _cls()
            ui_banner()
            print(_c("97;1", "  DESCARGAR MANGA\n"))
            url = _ask(_c("96;1", "  URL / ID > "))
            if not url:
                continue
            output   = _ask_output_path()
            conv_fmt = _ask_conv_format()
            process_download(url, output, conv_fmt, cookies=None)
            _pause()

        elif op == "2":
            _cls()
            ui_banner()
            print(_c("97;1", "  DESCARGA EN LOTE\n"))
            from utils.BatchManager import BATCH_FILE, ensure_batch_file, load_urls, run_batch
            print(_c("90", f"  Archivo de lista: {BATCH_FILE}\n"))
            if not ensure_batch_file():
                _pause()
                continue
            urls = load_urls()
            if not urls:
                print(_c("93;1", "  [!] lista.txt no contiene URLs válidas."))
                print(_c("90",   f"      Edita el archivo y añade una URL por línea."))
                _pause()
                continue

            print(_c("92;1", f"  {len(urls)} URL(s) encontradas."))
            output   = _ask_output_path()
            conv_fmt = _ask_conv_format()

            total = len(urls)

            def _fn(url, out, fmt, cook):
                idx = urls.index(url) + 1
                return process_download(url, out, fmt, cook, idx, total)

            run_batch(urls, _fn, output, conv_fmt, cookies=None)
            _pause()

        elif op == "3":
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

        elif op == "4":
            break


if __name__ == "__main__":
    main()