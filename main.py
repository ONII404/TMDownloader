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

# ── Imports normales ──────────────────────────────────────────────────────────
import argparse

from core.Session        import SessionManager
from core.DownloadEngine import DownloadEngine
from core.ScraperFactory import ScraperFactory
from utils.FileManager   import FileManager
from utils.history       import HistoryManager
from utils.config        import get_output_path, save_config, load_config
from utils.ui            import ui_banner, _c, _cls, _pause, _ask


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
    sep     = "═" * 50
    title   = meta.get("Title",  cid)
    series  = meta.get("Series", "")
    source  = meta.get("Source", "")
    chapter = meta.get("Number", "")

    print()
    print(_c("96", f"  {sep}"))

    if total > 1:
        print(_c("97;1", f"  Descarga  [{index} / {total}]"))
    else:
        print(_c("97;1",  "  Descarga"))

    if series and series != title:
        print(_c("97",  "  Serie   : ") + _c("93;1", series))
        print(_c("97",  "  Capítulo: ") + _c("93;1", title))
    else:
        print(_c("97",  "  Título  : ") + _c("93;1", title))

    if chapter and chapter != "1":
        print(_c("97",  "  Número  : ") + _c("90",   chapter))

    if source:
        print(_c("97",  "  Fuente  : ") + _c("90",   source))

    print(_c("96", f"  {sep}"))


# ── Descarga multi-capítulo (serie completa) ──────────────────────────────────

def _download_series(
    scraper,
    session,
    engine: DownloadEngine,
    url: str,
    output_path: str,
    conv_format: str | None,
) -> bool:
    print(_c("90", "\n  Obteniendo metadata de la serie..."), end="", flush=True)
    series_meta = scraper.get_series_metadata(session, url)
    series_name = series_meta.get("Series") or series_meta.get("Title", "")
    print(_c("92", " ✓"))
    print(_c("97", "  Serie   : ") + _c("93;1", series_name))

    print(_c("90", "  Obteniendo lista de capítulos..."), end="", flush=True)
    chapters = scraper.get_chapters(session, url)

    if not chapters:
        print(_c("91;1", " ✗"))
        print(_c("91;1", "  [!] No se encontraron capítulos."))
        return False

    print(_c("92", f" ✓  ({len(chapters)} capítulos)"))

    ok     = 0
    failed = []
    total  = len(chapters)

    for i, chapter in enumerate(chapters, 1):
        chapter_url  = scraper._BASE + chapter["url"]
        chapter_cid  = scraper.extract_id(chapter_url)
        dest_dir     = FileManager.prepare_dir(output_path, chapter_cid)
        chapter_meta = scraper.build_chapter_metadata(series_meta, chapter)

        _print_download_header(i, total, chapter_meta, chapter_cid)

        print(_c("90", "  Buscando imágenes..."), end="", flush=True)
        tasks = scraper.get_chapter_image_tasks(session, chapter, dest_dir, url)

        if not tasks:
            print(_c("91;1", " ✗  (sin imágenes)"))
            failed.append(chapter.get("titulo", str(i)))
            continue

        print(_c("92", f" ✓  ({len(tasks)} imágenes)"))
        print()

        success = engine.download_manga(
            tasks,
            title=chapter_meta.get("Title", ""),
        )

        if success:
            cbz_file = FileManager.compress_and_clean(
                dest_dir,
                meta=chapter_meta,
                conv_format=conv_format,
                series_name=series_name,
            )
            print(_c("92;1", f"\n  ✓  Guardado en: {cbz_file}"))
            ok += 1
        else:
            print(_c("93;1", "\n  ⚠  Descarga incompleta."))
            failed.append(chapter.get("titulo", str(i)))

    sep = "─" * 50
    print(_c("90",   f"\n  {sep}"))
    print(_c("97;1",  "  RESUMEN DE SERIE"))
    print(_c("92;1",  f"  ✓ Completados : {ok} / {total}"))
    if failed:
        print(_c("91;1", f"  ✗ Fallidos    : {len(failed)}"))
        for t in failed:
            print(_c("91",  f"    - {t}"))
    print(_c("90", f"  {sep}\n"))

    return len(failed) == 0


# ── process_download (entrada principal) ──────────────────────────────────────

def process_download(
    url: str,
    output_path: str,
    conv_format: str | None,
    cookies: str | None,
    batch_index: int = 1,
    batch_total: int = 1,
) -> bool:
    scraper = ScraperFactory.get_scraper(url)
    if not scraper:
        print(_c("91;1", f"\n  [!] No hay soporte para esta URL: {url}"))
        return False

    sm      = SessionManager(cookies_file=cookies)
    session = sm.get_session()
    engine  = DownloadEngine(session, max_workers=8)

    # ── Multi-capítulo ────────────────────────────────────────────────────────
    if hasattr(scraper, "is_multi_chapter") and scraper.is_multi_chapter(url):
        success = _download_series(scraper, session, engine, url, output_path, conv_format)
        if success:
            HistoryManager().add(url)
        return success

    # ── Capítulo individual / Oneshot ─────────────────────────────────────────
    cid = scraper.extract_id(url)

    print(_c("90", "\n  Obteniendo metadata..."), end="", flush=True)
    meta = scraper.get_metadata(session, cid)
    print(_c("92", " ✓"))

    series_name = meta.get("Series") or None
    dest_dir    = FileManager.prepare_dir(output_path, cid)

    _print_download_header(batch_index, batch_total, meta, cid)

    print(_c("90", "  Buscando imágenes..."), end="", flush=True)
    tasks = scraper.get_image_tasks(session, cid, dest_dir)

    if not tasks:
        print(_c("91;1", " ✗"))
        print(_c("91;1", "  [!] No se encontraron imágenes o el sitio bloqueó la petición."))
        return False

    print(_c("92", f" ✓  ({len(tasks)} imágenes)"))
    print()

    success = engine.download_manga(tasks, title=meta.get("Title", cid))

    if success:
        cbz_file = FileManager.compress_and_clean(
            dest_dir,
            meta=meta,
            conv_format=conv_format,
            series_name=series_name,
        )
        HistoryManager().add(url)
        print(_c("92;1", f"\n  ✓  Guardado en: {cbz_file}"))
    else:
        print(_c("93;1", "\n  ⚠  Descarga incompleta — archivos en:"))
        print(_c("90",   f"     {dest_dir}"))

    return success


# ── Lógica de lote con detección de modo ──────────────────────────────────────

def _run_batch_auto(
    urls: list[str],
    output_path: str,
    conv_format,
    cookies,
):
    """
    Decide automáticamente si usar modo normal o modo profundo
    según el número de URLs y el umbral configurado.
    """
    from utils.BatchManager import (
        run_batch, run_deep_batch,
        DELAY_BETWEEN_DOWNLOADS,
    )
    from utils.config import load_config

    cfg       = load_config()
    threshold = cfg.get("deep_mode_threshold", 10)
    total     = len(urls)

    if total > threshold:
        # ── Modo Profundo ─────────────────────────────────────────────────────
        print(_c("93;1", f"\n  [!] {total} URLs detectadas — activando Modo Profundo"))

        def _fn(url, out, fmt, cook):
            return process_download(url, out, fmt, cook, 1, 1)

        run_deep_batch(urls, _fn, output_path, conv_format, cookies)
    else:
        # ── Modo Normal ───────────────────────────────────────────────────────
        total_n = len(urls)

        def _fn(url, out, fmt, cook):
            idx = urls.index(url) + 1
            return process_download(url, out, fmt, cook, idx, total_n)

        run_batch(urls, _fn, output_path, conv_format, cookies,
                  delay=DELAY_BETWEEN_DOWNLOADS)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="TMD Manga Downloader")
    parser.add_argument("url",       nargs="?",              help="URL de un manga o capítulo")
    parser.add_argument("--batch",   "-b", action="store_true",
                        help="Modo lote (lee lista.txt)")
    parser.add_argument("--output",  "-o",                   help="Ruta de salida")
    parser.add_argument("--cookies", "-c",                   help="Archivo de cookies")
    parser.add_argument("--format",  "-f", choices=["jpg", "avif"],
                        help="Convertir imágenes a este formato")
    args = parser.parse_args()

    output = args.output or get_output_path()

    if args.url:
        process_download(args.url, output, args.format, args.cookies)
        return

    if args.batch:
        from utils.BatchManager import ensure_batch_file, load_urls
        if not ensure_batch_file():
            return
        urls = load_urls()
        if not urls:
            print(_c("93;1", "[!] lista.txt no contiene URLs válidas."))
            return
        _run_batch_auto(urls, output, args.format, args.cookies)
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
        print("  [4] Configuración")
        print("  [5] Salir")

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
            from utils.BatchManager import BATCH_FILE, ensure_batch_file, load_urls
            print(_c("90", f"  Archivo de lista: {BATCH_FILE}\n"))
            if not ensure_batch_file():
                _pause()
                continue
            urls = load_urls()
            if not urls:
                print(_c("93;1", "  [!] lista.txt no contiene URLs válidas."))
                print(_c("90",   "      Edita el archivo y añade una URL por línea."))
                _pause()
                continue

            cfg       = load_config()
            threshold = cfg.get("deep_mode_threshold", 10)
            print(_c("92;1", f"  {len(urls)} URL(s) encontradas."))
            if len(urls) > threshold:
                print(_c("93;1", f"  → Se activará Modo Profundo (>{threshold} URLs)"))
            output   = _ask_output_path()
            conv_fmt = _ask_conv_format()
            _run_batch_auto(urls, output, conv_fmt, cookies=None)
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
            _show_config_menu()

        elif op == "5":
            break


# ── Menú de configuración ─────────────────────────────────────────────────────

def _show_config_menu():
    from utils.config import load_config, save_config, list_user_agents

    _cls()
    ui_banner()
    cfg = load_config()

    print(_c("97;1", "  CONFIGURACIÓN\n"))

    threshold   = cfg.get("deep_mode_threshold", 10)
    batch_size  = cfg.get("batch_size", 25)
    dl_delay    = cfg.get("delay_between_downloads", [5, 9])
    lot_delay   = cfg.get("delay_between_batches", [480, 900])
    vpn_every   = cfg.get("vpn_remind_every", [4, 7])
    cf_wait     = cfg.get("cf_wait_seconds", [7200, 14400])
    ua_current  = cfg.get("user_agent", None) or "(rotación automática)"
    ua_rotate   = cfg.get("ua_rotate_every_batches", 3)

    print(_c("97", f"  [1] Umbral modo profundo     : {threshold} URLs"))
    print(_c("97", f"  [2] Tamaño de lote           : {batch_size} URLs"))
    print(_c("97", f"  [3] Delay entre descargas    : {dl_delay[0]}-{dl_delay[1]}s"))
    print(_c("97", f"  [4] Delay entre lotes        : {lot_delay[0]//60}-{lot_delay[1]//60} min"))
    print(_c("97", f"  [5] Aviso VPN cada N lotes   : {vpn_every[0]}-{vpn_every[1]}"))
    print(_c("97", f"  [6] Espera Cloudflare        : {cf_wait[0]//3600}-{cf_wait[1]//3600}h"))
    print(_c("97", f"  [7] User-Agent actual        : {ua_current[:60]}"))
    print(_c("97", f"  [8] Rotar UA cada N lotes    : {ua_rotate} (0=desactivado)"))
    print(_c("97",  "  [9] Volver"))

    op = _ask(_c("93;1", "\n  Opción > "))

    if op == "1":
        val = _ask(f"  Nuevo umbral [{threshold}] > ")
        if val.isdigit():
            save_config({"deep_mode_threshold": int(val)})
    elif op == "2":
        val = _ask(f"  Nuevo tamaño de lote [{batch_size}] > ")
        if val.isdigit():
            save_config({"batch_size": int(val)})
    elif op == "3":
        mn = _ask(f"  Delay mínimo [{dl_delay[0]}s] > ")
        mx = _ask(f"  Delay máximo [{dl_delay[1]}s] > ")
        if mn.isdigit() and mx.isdigit():
            save_config({"delay_between_downloads": [int(mn), int(mx)]})
    elif op == "4":
        mn = _ask(f"  Delay mínimo en minutos [{lot_delay[0]//60}] > ")
        mx = _ask(f"  Delay máximo en minutos [{lot_delay[1]//60}] > ")
        if mn.isdigit() and mx.isdigit():
            save_config({"delay_between_batches": [int(mn)*60, int(mx)*60]})
    elif op == "5":
        mn = _ask(f"  Cada mínimo [{vpn_every[0]}] lotes > ")
        mx = _ask(f"  Cada máximo [{vpn_every[1]}] lotes > ")
        if mn.isdigit() and mx.isdigit():
            save_config({"vpn_remind_every": [int(mn), int(mx)]})
    elif op == "6":
        mn = _ask(f"  Espera mínima en horas [{cf_wait[0]//3600}] > ")
        mx = _ask(f"  Espera máxima en horas [{cf_wait[1]//3600}] > ")
        if mn.isdigit() and mx.isdigit():
            save_config({"cf_wait_seconds": [int(mn)*3600, int(mx)*3600]})
    elif op == "7":
        uas = list_user_agents()
        print(_c("97;1", "\n  User-Agents disponibles:"))
        print(_c("90",   "  [0] Rotación automática (recomendado)"))
        for i, ua in enumerate(uas, 1):
            print(_c("90", f"  [{i}] {ua[:80]}"))
        custom_lbl = len(uas) + 1
        print(_c("90",   f"  [{custom_lbl}] Personalizado"))
        sel = _ask(_c("93;1", "  Opción > "))
        if sel == "0":
            save_config({"user_agent": None})
        elif sel.isdigit() and 1 <= int(sel) <= len(uas):
            save_config({"user_agent": uas[int(sel) - 1]})
        elif sel == str(custom_lbl):
            custom = _ask("  Introduce tu User-Agent > ")
            if custom:
                save_config({"user_agent": custom})
    elif op == "8":
        val = _ask(f"  Rotar cada N lotes [{ua_rotate}] (0=desactivado) > ")
        if val.isdigit():
            save_config({"ua_rotate_every_batches": int(val)})

    if op != "9":
        print(_c("92", "\n  ✓ Configuración guardada."))
        _pause()


if __name__ == "__main__":
    main()