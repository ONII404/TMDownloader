#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TMOHentai Downloader - Termux/Android
Descarga imágenes directamente del CDN.

Patrón CDN (ingeniería inversa):
    https://cache{1-4}.tmohentai.com/contents/{ID}/{000..N}.webp

USO:
    python3 tmohentai_downloader.py https://tmohentai.com/contents/69adc7143c985
    python3 tmohentai_downloader.py https://tmohentai.com/reader/69adc7143c985/cascade
    python3 tmohentai_downloader.py 69adc7143c985       # ID directo

Las imágenes se guardan en:
    /storage/emulated/0/WhatsAppZips/{ID}/
"""

# ── Auto-instalación ──────────────────────────────────────────────────────────
import subprocess, sys, os

def _ensure_deps():
    if os.environ.get("_TMODL_OK"):
        return
    needed = [("requests", "requests"), ("cloudscraper", "cloudscraper")]
    missing = []
    for mod, pkg in needed:
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if not missing:
        os.environ["_TMODL_OK"] = "1"
        return
    print("[SETUP] Instalando: " + ", ".join(missing))
    for pkg in missing:
        ok = False
        for cmd in [
            [sys.executable, "-m", "pip", "install", pkg, "--break-system-packages", "-q"],
            [sys.executable, "-m", "pip", "install", pkg, "-q"],
        ]:
            try:
                if subprocess.run(cmd, capture_output=True, timeout=120).returncode == 0:
                    print(f"  OK  {pkg}")
                    ok = True
                    break
            except Exception:
                continue
        if not ok:
            print(f"  ERROR: pip install {pkg} --break-system-packages")
            sys.exit(1)
    os.environ["_TMODL_OK"] = "1"
    print("[SETUP] Listo. Recargando...\n")
    os.execv(sys.executable, [sys.executable] + sys.argv)

_ensure_deps()

# ── Imports ───────────────────────────────────────────────────────────────────
import re, time, argparse
from pathlib import Path
from urllib.parse import urlparse

import requests, urllib3
urllib3.disable_warnings()


# ── Color helper (disponible para run() y la UI) ─────────────────────────────
def _c(code: str, text: str) -> str:
    """Aplica color ANSI si el terminal lo soporta, si no devuelve texto plano."""
    if not sys.stdout.isatty():
        return text
    return "\033[" + code + "m" + text + "\033[0m"

# ── Constantes ────────────────────────────────────────────────────────────────
OUT_BASE = "/storage/emulated/0/WhatsAppZips"

CDN_HOSTS = [
    "cache1.tmohentai.com",
    "cache2.tmohentai.com",
    "cache3.tmohentai.com",
    "cache4.tmohentai.com",
]

EXTS = [".webp", ".jpg", ".jpeg", ".png", ".gif"]

UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Mobile Safari/537.36"
)

# Palabras que no son IDs
_RESERVED = {
    "index.php","contents","reader","g","cascade","paginated",
    "search","tags","category","page","home","login","register","latest","popular",
}

# ── Sesión ────────────────────────────────────────────────────────────────────
def make_session(cookies_file=None):
    try:
        import cloudscraper
        s = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "android", "mobile": True},
            delay=3,
        )
    except Exception:
        s = requests.Session()

    s.headers.update({
        "User-Agent": UA,
        "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9",
        "Connection": "keep-alive",
    })

    if cookies_file:
        try:
            import http.cookiejar
            jar = http.cookiejar.MozillaCookieJar(cookies_file)
            jar.load(ignore_discard=True, ignore_expires=True)
            s.cookies.update(jar)
            print(f"[COOKIES] Cargadas: {cookies_file}")
        except Exception as e:
            print(f"[COOKIES] Error: {e}")

    return s


# ── Extraer ID ────────────────────────────────────────────────────────────────
def extract_id(raw: str) -> str:
    """
    Acepta:
      - ID directo:          69adc7143c985
      - URL contents:        https://tmohentai.com/contents/69adc7143c985
      - URL index.php:       https://tmohentai.com/index.php/contents/69adc7143c985
      - URL reader cascade:  https://tmohentai.com/reader/69adc7143c985/cascade
      - URL reader paginated:https://tmohentai.com/reader/69adc7143c985/paginated/1
      - URL imagen CDN:      https://cache1.tmohentai.com/contents/69adc7143c985/000.webp
    """
    raw = raw.strip()

    # Si no contiene "/" puede ser un ID directo
    if "/" not in raw and re.match(r'^[a-zA-Z0-9]+$', raw) and raw.lower() not in _RESERVED:
        return raw

    # Patrones en orden de especificidad
    for pattern in (
        r"/contents/([a-zA-Z0-9]+)",
        r"/reader/([a-zA-Z0-9]+)",
        r"/g/([a-zA-Z0-9]+)",
    ):
        m = re.search(pattern, raw)
        if m:
            cid = m.group(1)
            if cid.lower() not in _RESERVED:
                return cid

    # Fallback: último segmento alfanumérico válido
    for part in reversed(urlparse(raw).path.strip("/").split("/")):
        if re.match(r'^[a-zA-Z0-9]+$', part) and part.lower() not in _RESERVED:
            return part

    return ""


# ── Descargar una imagen ──────────────────────────────────────────────────────
def download_image(sess, cid: str, index: int, dest_dir: Path, referer: str) -> bool:
    """
    Intenta descargar la imagen `index` probando todos los CDN hosts y extensiones.
    Retorna True si descargó algo válido (>= 512 bytes).
    """
    hdrs = {
        "Referer":        referer,
        "Accept":         "image/webp,image/apng,image/*,*/*;q=0.8",
        "Sec-Fetch-Dest": "image",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-site",
    }

    # Rotar host CDN según el índice (igual que hace el navegador)
    host_order = CDN_HOSTS[index % len(CDN_HOSTS):] + CDN_HOSTS[:index % len(CDN_HOSTS)]

    for ext in EXTS:
        for host in host_order:
            url  = f"https://{host}/contents/{cid}/{index:03d}{ext}"
            dest = dest_dir / f"{index:03d}{ext}"

            # Ya existe y es válida
            if dest.exists() and dest.stat().st_size >= 512:
                return True

            for verify in (True, False):
                try:
                    r = sess.get(url, headers=hdrs, timeout=30,
                                 stream=True, verify=verify)

                    if r.status_code == 404:
                        break   # Esta ext/host no existe, probar siguiente

                    r.raise_for_status()

                    ct = r.headers.get("Content-Type", "")
                    if "text/html" in ct:
                        break

                    with open(dest, "wb") as f:
                        for chunk in r.iter_content(8192):
                            if chunk:
                                f.write(chunk)

                    if dest.stat().st_size >= 512:
                        return True   # ¡Éxito!

                    dest.unlink(missing_ok=True)

                except requests.exceptions.SSLError:
                    if verify:
                        continue   # Reintentar sin verificación SSL
                    break
                except Exception:
                    dest.unlink(missing_ok=True)
                    break

    return False


# ── Descarga principal ────────────────────────────────────────────────────────
def run(cid: str, sess, out_base: str = OUT_BASE, max_images: int = 1000):
    dest_dir = Path(out_base) / cid
    dest_dir.mkdir(parents=True, exist_ok=True)

    referer = f"https://tmohentai.com/reader/{cid}/cascade?image-width=normal-width"

    print(_c("96;1", "\n" + "═" * 55))
    print(_c("97;1",  "  TMOHentai Downloader"))
    print(_c("96;1", "═" * 55))
    print("  " + _c("90", "ID      :") + " " + _c("96;1", cid))
    print("  " + _c("90", "Carpeta :") + " " + _c("97", str(dest_dir)))
    print("  " + _c("90", "Patron  :") + " " + _c("90", "https://cache1.tmohentai.com/contents/" + cid + "/000.webp"))
    print(_c("90", "─" * 55))

    ok     = 0
    fails  = 0        # Fallos consecutivos
    index  = 0

    while index < max_images:
        success = download_image(sess, cid, index, dest_dir, referer)

        if success:
            # Encontrar el archivo que se creó
            saved = None
            for ext in EXTS:
                p = dest_dir / f"{index:03d}{ext}"
                if p.exists() and p.stat().st_size >= 512:
                    saved = p
                    break
            size = f"{saved.stat().st_size // 1024}KB" if saved else "?"
            print("  " + _c("92;1", "OK") + "  " + _c("90", f"[{index:03d}]") + "  " + _c("97", saved.name if saved else "?") + "  " + _c("90", "(" + size + ")"))
            ok    += 1
            fails  = 0   # Resetear contador de fallos consecutivos
        else:
            fails += 1
            print("  " + _c("90", "--") + "  " + _c("90", f"[{index:03d}]") + "  " + _c("90", "no encontrada"))

            # Si hay 3 fallos consecutivos, el manga terminó
            if fails >= 3:
                print(_c("93;1", "\n  [FIN] 3 imágenes consecutivas no encontradas — manga completo."))
                break

        index += 1
        time.sleep(0.25)   # Rate limiting suave

    print(_c("90", "─" * 55))
    print("  " + _c("90", "Total descargadas :") + " " + _c("92;1", str(ok)))
    print("  " + _c("90", "Guardadas en      :") + " " + _c("97", str(dest_dir)))
    print(_c("96;1", "═" * 55 + "\n"))
    return ok


# =============================================================================
#  UI — Funciones auxiliares (no tocan el código base)
# =============================================================================

def _cls():
    os.system("clear" if os.name != "nt" else "cls")

def _pause(msg="  Pulsa Enter para continuar..."):
    try:
        input(_c("90", msg))
    except (EOFError, KeyboardInterrupt):
        pass

def _ask(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


# ─────────────────────────────────────────────────────────────────────────────
#  BANNER
# ─────────────────────────────────────────────────────────────────────────────


# =============================================================================
#  HISTORIAL DE DESCARGAS
# =============================================================================
import datetime as _dt

_HIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          ".tmohentai_history.txt")


def _hist_add(url: str):
    """Agrega una URL al historial con fecha y hora."""
    try:
        ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(_HIST_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}]  {url}\n")
    except Exception:
        pass


def ui_history():
    """Muestra el historial de descargas."""
    _cls()
    ui_banner()
    print(_c("93;1", "  HISTORIAL DE DESCARGAS"))
    print(_c("90",   "  " + "─" * 43))
    print()
    try:
        with open(_HIST_FILE, "r", encoding="utf-8") as f:
            lines = [l.rstrip() for l in f if l.strip()]
        if not lines:
            print(_c("90", "  El historial está vacío."))
        else:
            for line in lines[-50:]:   # mostrar las últimas 50
                # Separar timestamp de URL para colorearlos
                if line.startswith("[") and "]  " in line:
                    ts, url = line.split("]  ", 1)
                    print("  " + _c("90", ts + "]") + "  " + _c("96", url))
                else:
                    print("  " + line)
            if len(lines) > 50:
                print(_c("90", f"\n  ... y {len(lines)-50} entradas anteriores."))
    except FileNotFoundError:
        print(_c("90", "  Aún no se ha descargado nada."))
    except Exception as e:
        print(_c("91", f"  Error leyendo historial: {e}"))
    print()
    print(_c("90", "  " + "─" * 43))
    _pause()


def ui_banner():
    print()
    print(_c("96;1", "  ████████╗███╗   ███╗ ██████╗ "))
    print(_c("96;1", "     ██╔══╝████╗ ████║██╔═══██╗"))
    print(_c("97;1", "     ██║   ██╔████╔██║██║   ██║"))
    print(_c("97;1", "     ██║   ██║╚██╔╝██║██║   ██║"))
    print(_c("93;1", "     ██║   ██║ ╚═╝ ██║╚██████╔╝"))
    print(_c("93;1", "     ╚═╝   ╚═╝     ╚═╝ ╚═════╝ "))
    print()
    print(_c("90", "  ") + _c("96", "Hentai Downloader") +
          _c("90", "  •  CDN directo  •  Termux/Android"))
    print(_c("90", "  " + "─" * 43))
    print()

# ─────────────────────────────────────────────────────────────────────────────
#  AYUDA
# ─────────────────────────────────────────────────────────────────────────────

def ui_help():
    _cls()
    ui_banner()
    print(_c("93;1", "  AYUDA — Cómo usar esta herramienta"))
    print(_c("90",   "  " + "─" * 43))
    print()
    print(_c("97;1", "  ¿Qué hace?"))
    print("    Descarga todas las imágenes de un manga de")
    print("    tmohentai.com directamente desde su CDN.")
    print()
    print(_c("97;1", "  ¿Dónde guarda el resultado?"))
    print("    " + _c("96", OUT_BASE + "/{ID}.zip"))
    print("    Cada manga queda comprimido en un solo .zip.")
    print("    La carpeta temporal de descarga se borra sola.")
    print()
    print(_c("97;1", "  ¿Qué URLs acepta?"))
    print("    " + _c("93", "•") + " URL de galería:")
    print("        https://tmohentai.com/contents/69adc7143c985")
    print("    " + _c("93", "•") + " URL con index.php:")
    print("        https://tmohentai.com/index.php/contents/69adc7143c985")
    print("    " + _c("93", "•") + " URL del reader:")
    print("        https://tmohentai.com/reader/69adc7143c985/cascade")
    print("    " + _c("93", "•") + " ID directo:")
    print("        69adc7143c985")
    print()
    print(_c("97;1", "  ¿Cómo sé cuándo termina?"))
    print("    Para automáticamente cuando 3 imágenes")
    print("    consecutivas no se encuentran en el CDN.")
    print()
    print(_c("97;1", "  ¿Qué pasa si Cloudflare bloquea?"))
    print("    1. Instala 'Get cookies.txt LOCALLY' en tu navegador")
    print("    2. Visita tmohentai.com y exporta las cookies")
    print("    3. Ejecuta con el argumento --cookies:")
    print("       " + _c("96", "python3 tmohentai_downloader.py --cookies cookies.txt"))
    print()
    print(_c("97;1", "  Uso desde la terminal (sin menú):"))
    print("    " + _c("96", "python3 tmohentai_downloader.py <URL>"))
    print("    " + _c("96", "python3 tmohentai_downloader.py <URL> --cookies cookies.txt"))
    print("    " + _c("96", "python3 tmohentai_downloader.py <URL> --output /sdcard/Mangas"))
    print()
    print(_c("90", "  " + "─" * 43))
    _pause()


# ─────────────────────────────────────────────────────────────────────────────
#  COMPRIMIR Y LIMPIAR
# ─────────────────────────────────────────────────────────────────────────────

def compress_and_clean(folder: Path) -> Path:
    """
    Comprime `folder` en {folder}.zip y luego BORRA la carpeta original.
    El único producto final es el .zip — sin residuos.
    """
    import zipfile
    import shutil

    zip_path = folder.parent / (folder.name + ".zip")

    print()
    print(_c("93;1", "  [ZIP] Comprimiendo..."))

    files = sorted(f for f in folder.iterdir() if f.is_file())
    total = len(files)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for i, f in enumerate(files, 1):
            zf.write(f, arcname=f.name)
            pct = int(i / total * 30)
            bar = "█" * pct + "░" * (30 - pct)
            line = "\r  " + _c("96", bar) + "  " + str(i) + "/" + str(total)
            print(line, end="", flush=True)

    print()
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(_c("92;1", "  [ZIP] Listo  →  " + str(zip_path)))
    print(_c("90",   "         Tamaño: " + f"{size_mb:.1f}" + " MB"))

    # Borrar carpeta temporal — el .zip es el único producto final
    try:
        shutil.rmtree(folder)
        print(_c("90", "  [ZIP] Carpeta temporal eliminada"))
    except Exception as exc:
        print(_c("91", "  [!] No se pudo borrar la carpeta: " + str(exc)))

    return zip_path


# ─────────────────────────────────────────────────────────────────────────────
#  FLUJO INTERACTIVO DE DESCARGA
# ─────────────────────────────────────────────────────────────────────────────

def ui_download(out_base: str = OUT_BASE, cookies_file: str = None,
                max_images: int = 1000):
    _cls()
    ui_banner()
    print(_c("97;1", "  DESCARGAR MANGA"))
    print(_c("90",   "  " + "─" * 43))
    print()
    print("  Pega la URL o el ID del manga")
    print(_c("90", "  (Enter vacío para cancelar)"))
    print()

    raw = _ask(_c("96;1", "  URL / ID › "))
    if not raw:
        print(_c("90", "\n  Cancelado."))
        _pause()
        return

    cid = extract_id(raw)
    if not cid:
        print()
        print(_c("91;1", "  [ERROR] No se pudo extraer el ID."))
        print(_c("90",   "  Formatos válidos:"))
        print("    https://tmohentai.com/contents/69adc7143c985")
        print("    https://tmohentai.com/reader/69adc7143c985/cascade")
        print("    69adc7143c985")
        _pause()
        return

    dest_dir = Path(out_base) / cid
    zip_path = dest_dir.parent / (cid + ".zip")

    print()
    print(_c("90", "  " + "─" * 43))
    print("  " + _c("90", "ID detectado  :") + " " + _c("96;1", cid))
    print("  " + _c("90", "ZIP final     :") + " " + _c("97", str(zip_path)))
    print(_c("90", "  " + "─" * 43))
    print()
    resp = _ask(_c("93;1", "  ¿Confirmar descarga? [s/n] › "))
    if resp.lower() not in ("s", "si", "sí", "y", "yes"):
        print(_c("90", "\n  Cancelado."))
        _pause()
        return

    _hist_add(raw)   # guardar URL en historial
    print()
    sess = make_session(cookies_file)
    ok   = run(cid, sess, out_base=out_base, max_images=max_images)

    if ok == 0:
        print(_c("91;1", "\n  [!] No se descargó ninguna imagen."))
        print(_c("90",   "      Si ves errores 403, usa --cookies cookies.txt"))
        _pause()
        return

    try:
        compress_and_clean(dest_dir)
    except Exception as exc:
        print(_c("91", "\n  [!] Error al comprimir: " + str(exc)))

    print()
    _pause(_c("92;1", "  ✓ Completado. Pulsa Enter para volver al menú..."))


# ─────────────────────────────────────────────────────────────────────────────
#  MENÚ PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def ui_menu(out_base: str = OUT_BASE, cookies_file: str = None,
            max_images: int = 1000):
    while True:
        _cls()
        ui_banner()
        print(_c("97;1", "  MENÚ PRINCIPAL"))
        print(_c("90",   "  " + "─" * 43))
        print()
        print("  " + _c("96;1", "[1]") + "  Descargar manga")
        print("  " + _c("96;1", "[2]") + "  Ayuda")
        print("  " + _c("96;1", "[3]") + "  Salir")
        print("  " + _c("96;1", "[4]") + "  Historial")
        print()

        opcion = _ask(_c("93;1", "  Opción › "))

        if opcion == "1":
            ui_download(out_base=out_base, cookies_file=cookies_file,
                        max_images=max_images)
        elif opcion == "2":
            ui_help()
        elif opcion in ("3", "q", "exit", "salir"):
            _cls()
            print(_c("90", "\n  Hasta luego.\n"))
            sys.exit(0)
        elif opcion == "4":
            ui_history()
        else:
            print(_c("91", "\n  Opción no válida."))
            _pause("  Pulsa Enter...")


# =============================================================================
#  ENTRADA PRINCIPAL
# =============================================================================
def main():
    ap = argparse.ArgumentParser(
        description="Descarga mangas de tmohentai.com vía CDN directo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python3 tmohentai_downloader.py https://tmohentai.com/contents/69adc7143c985\n"
            "  python3 tmohentai_downloader.py https://tmohentai.com/reader/69adc7143c985/cascade\n"
            "  python3 tmohentai_downloader.py 69adc7143c985\n"
            "  python3 tmohentai_downloader.py <URL> --cookies cookies.txt\n"
            "\n"
            "Si Cloudflare bloquea:\n"
            "  1. Instala 'Get cookies.txt LOCALLY' en Chrome/Firefox\n"
            "  2. Descarga las cookies de tmohentai.com\n"
            "  3. Usa: python3 tmohentai_downloader.py <URL> --cookies cookies.txt\n"
        ),
    )
    ap.add_argument("url", nargs="?", default=None,
                    help="URL del manga o ID directo")
    ap.add_argument("--output", "-o", default=OUT_BASE,
                    help="Carpeta base de salida (default: " + OUT_BASE + ")")
    ap.add_argument("--cookies", "-c", default=None, metavar="FILE",
                    help="Archivo cookies.txt para bypass de Cloudflare")
    ap.add_argument("--max", "-m", type=int, default=1000,
                    help="Límite máximo de imágenes a intentar (default: 1000)")

    args = ap.parse_args()

    # Sin URL → menú interactivo
    if not args.url:
        ui_menu(out_base=args.output, cookies_file=args.cookies,
                max_images=args.max)
        return

    # Con URL → modo directo (comportamiento original + comprimir + limpiar)
    cid = extract_id(args.url)
    if not cid:
        print("\n[ERROR] No se pudo extraer el ID de: " + repr(args.url))
        print("  Ejemplos válidos:")
        print("    https://tmohentai.com/contents/69adc7143c985")
        print("    https://tmohentai.com/reader/69adc7143c985/cascade")
        print("    69adc7143c985")
        sys.exit(1)

    sess = make_session(args.cookies)
    ok   = run(cid, sess, out_base=args.output, max_images=args.max)

    if ok > 0:
        dest_dir = Path(args.output) / cid
        try:
            compress_and_clean(dest_dir)
        except Exception as exc:
            print("[!] Error al comprimir: " + str(exc))

    sys.exit(0 if ok > 0 else 1)


if __name__ == "__main__":
    main()
