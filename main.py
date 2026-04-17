# main.py
import sys
import argparse
from pathlib import Path

from core.Session import SessionManager
from core.DownloadEngine import DownloadEngine
from core.ScraperFactory import ScraperFactory
from utils.FileManager import FileManager
from utils.history import HistoryManager
from utils.ui import ui_banner, _c, _cls, _pause, _ask

def process_download(url, args):
    # 1. Identificar el sitio (Factory)
    scraper = ScraperFactory.get_scraper(url)
    if not scraper:
        print(_c("91;1", f"\n[!] No hay soporte para esta URL: {url}"))
        return

    # 2. Inicializar Sesión y Engine
    sm = SessionManager(cookies_file=args.cookies)
    engine = DownloadEngine(sm.get_session(), max_workers=8)

    # 3. Preparar metadatos y rutas
    cid = scraper.extract_id(url)
    dest_dir = FileManager.prepare_dir(args.output, cid)

    print(_c("96;1", f"\n[*] Iniciando descarga: {cid}"))
    print(_c("90", f"  Carpeta temporal: {dest_dir}"))

    # 4. Probing de imágenes (síncrono, necesario para saber cuántas hay)
    print(_c("93;1", "  Buscando imágenes en el CDN..."))
    tasks = scraper.get_image_tasks(sm.get_session(), cid, dest_dir)

    if not tasks:
        print(_c("91;1", "[!] No se encontraron imágenes o el sitio bloqueó la petición."))
        return

    print(_c("97;1", f"  {len(tasks)} imágenes encontradas. Descargando en paralelo...\n"))

    # 5. Descarga paralela
    success = engine.download_manga(tasks)

    # 6. Post-procesamiento
    if success:
        zip_file = FileManager.compress_and_clean(dest_dir)
        HistoryManager().add(url)  # Registrar en historial solo si fue exitoso
        print(_c("92;1", f"\n[OK] Exito! Archivo guardado en: {zip_file}"))
    else:
        print(_c("93;1", "\n[!] Descarga incompleta. Se conservaron los archivos temporales."))
        print(_c("90",   f"    Revisa los archivos en: {dest_dir}"))

def main():
    parser = argparse.ArgumentParser(description="Multi-Site Hentai Downloader")
    parser.add_argument("url", nargs="?", help="URL del manga")
    parser.add_argument("--output", "-o", default="/storage/emulated/0/WhatsAppZips", help="Ruta de salida")
    parser.add_argument("--cookies", "-c", help="Archivo de cookies")
    args = parser.parse_args()

    if args.url:
        process_download(args.url, args)
    else:
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
                url = _ask(_c("96;1", "  URL / ID > "))
                if url:
                    process_download(url, args)
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