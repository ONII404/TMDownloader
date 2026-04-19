# /utils/BatchManager.py
"""
Gestión de descargas en lote con dos modos:
  - Normal      : ≤ threshold URLs, comportamiento original.
  - Profundo    : > threshold URLs, lotes de N con delays aleatorios,
                  reanudación segura, detección de Cloudflare, aviso de VPN.
"""
import time
import random
from pathlib import Path

from utils.ui      import _c, _ask
from utils.config  import load_config
from utils.history import HistoryManager, ProgressState

# ── Constantes y rutas ────────────────────────────────────────────────────────

BATCH_FILE = Path(__file__).parent.parent / "lista.txt"

# Delays por defecto (sobreescritos por config)
DELAY_BETWEEN_DOWNLOADS = 5

_TEMPLATE = """\
# TMD - Lista de descargas en lote
# Una URL por línea. Las líneas que empiezan con # son comentarios.
# Puedes usar URLs completas de los sitios soportados.
#
# Ejemplos:
# https://tmohentai.com/contents/69b6fd0b4a6fa
# https://lectorhentai.com/manga/24514/loca-por-ti
"""

# Códigos HTTP que indican bloqueo de Cloudflare
_CF_STATUS_CODES = {429, 403, 503, 1015}
_CF_KEYWORDS     = ["cloudflare", "cf-ray", "challenge", "just a moment", "ddos"]


# ══════════════════════════════════════════════════════════════════════════════
# Helpers públicos
# ══════════════════════════════════════════════════════════════════════════════

def ensure_batch_file() -> bool:
    if BATCH_FILE.exists():
        return True
    BATCH_FILE.write_text(_TEMPLATE, encoding="utf-8")
    print(_c("93;1", f"\n  [!] No existía lista.txt — se creó la plantilla en:"))
    print(_c("90",   f"      {BATCH_FILE}"))
    print(_c("90",    "      Añade tus URLs y vuelve a elegir esta opción.\n"))
    return False


def load_urls() -> list[str]:
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


# ══════════════════════════════════════════════════════════════════════════════
# Detección de Cloudflare
# ══════════════════════════════════════════════════════════════════════════════

def is_cloudflare_block(status_code: int, response_text: str = "") -> bool:
    """Retorna True si la respuesta parece un bloqueo de Cloudflare."""
    if status_code in _CF_STATUS_CODES:
        return True
    lower = response_text.lower()
    return any(kw in lower for kw in _CF_KEYWORDS)


def handle_cloudflare_block(cfg: dict):
    """
    Muestra advertencia y espera el tiempo configurado antes de continuar.
    """
    wait_range = cfg.get("cf_wait_seconds", [7200, 14400])
    wait_secs  = random.randint(wait_range[0], wait_range[1])
    wait_mins  = wait_secs // 60
    wait_hrs   = wait_mins // 60

    sep = "═" * 52
    print()
    print(_c("91;1", f"  {sep}"))
    print(_c("91;1",  "  ⛔  BLOQUEO DE CLOUDFLARE DETECTADO"))
    print(_c("91;1", f"  {sep}"))
    print(_c("97",    "  Cloudflare ha bloqueado las peticiones (403/429/1015)."))
    print(_c("97",    "  El script esperará automáticamente antes de continuar."))
    print()
    print(_c("93;1", f"  ⏳ Esperando {wait_hrs}h {wait_mins % 60}m ({wait_secs}s)..."))
    print(_c("90",    "  Puedes dejar el script corriendo o cerrarlo."))
    print(_c("90",    "  Al reanudar, continuará desde la última URL completada."))
    print(_c("91;1", f"  {sep}\n"))

    _countdown(wait_secs)


def _countdown(seconds: int):
    """Muestra una cuenta regresiva en consola."""
    import sys
    for remaining in range(seconds, 0, -1):
        h = remaining // 3600
        m = (remaining % 3600) // 60
        s = remaining % 60
        line = _c("90", f"  ⏳ Reanudando en {h:02d}:{m:02d}:{s:02d}...")
        print(f"\r{line}", end="", flush=True)
        time.sleep(1)
    print()


# ══════════════════════════════════════════════════════════════════════════════
# Modo Normal
# ══════════════════════════════════════════════════════════════════════════════

def run_batch(
    urls: list[str],
    download_fn,
    output_path: str,
    conv_format,
    cookies,
    delay: int = DELAY_BETWEEN_DOWNLOADS,
) -> dict:
    """Descarga secuencial simple (modo normal, ≤ threshold URLs)."""
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

        if i < total and delay > 0:
            print(_c("90", f"\n  ⏳ Esperando {delay}s..."))
            time.sleep(delay)

    _print_batch_summary(ok, failed)
    return {"ok": ok, "failed": failed}


# ══════════════════════════════════════════════════════════════════════════════
# Modo Profundo
# ══════════════════════════════════════════════════════════════════════════════

def run_deep_batch(
    urls: list[str],
    download_fn,
    output_path: str,
    conv_format,
    cookies,
    session_obj=None,      # sesión HTTP para rotación de UA (opcional)
) -> dict:
    """
    Modo Descarga Profunda para listas grandes.
    - Lotes de batch_size URLs
    - Delays aleatorios entre descargas y entre lotes
    - Reanudación segura desde .tmd_progress.json
    - Detección de Cloudflare con espera automática
    - Avisos de cambio de VPN cada N lotes
    - Rotación de User-Agent
    """
    cfg = load_config()

    batch_size      = cfg.get("batch_size", 25)
    dl_delay_range  = cfg.get("delay_between_downloads", [5, 9])
    lot_delay_range = cfg.get("delay_between_batches", [480, 900])
    vpn_every_range = cfg.get("vpn_remind_every", [4, 7])
    ua_rotate_every = cfg.get("ua_rotate_every_batches", 3)

    history  = HistoryManager()
    progress = ProgressState()

    total_urls = len(urls)

    # ── Comprobar si se puede reanudar ────────────────────────────────────────
    can_resume, start_index = progress.resume_session(urls, BATCH_FILE)

    if can_resume and start_index > 0:
        sep = "═" * 52
        print()
        print(_c("93;1", f"  {sep}"))
        print(_c("93;1",  "  🔄  REANUDANDO SESIÓN ANTERIOR"))
        print(_c("97",   f"  Completadas : {start_index} / {total_urls} URLs"))
        print(_c("97",   f"  Continuando desde URL #{start_index + 1}"))
        print(_c("93;1", f"  {sep}\n"))
        confirm = _ask(_c("93;1", "  ¿Reanudar desde donde se quedó? [S/n] > "))
        if confirm.lower() == "n":
            progress.init_session(urls, BATCH_FILE)
            start_index = 0
    else:
        progress.init_session(urls, BATCH_FILE)
        start_index = 0

    # URLs pendientes desde el punto de reanudación
    pending_urls = urls[start_index:]

    # Calcular número de lotes totales (sobre lista completa para mostrar bien)
    total_batches  = (total_urls + batch_size - 1) // batch_size
    start_batch_n  = start_index // batch_size  # lote en que arrancamos

    ok_urls     = list(progress.completed_urls)
    failed_urls = list(progress.failed_urls)

    # Próximo aviso de VPN (en número de lote)
    vpn_remind_interval = random.randint(*vpn_every_range)
    next_vpn_reminder   = start_batch_n + vpn_remind_interval

    _print_deep_mode_header(total_urls, total_batches, batch_size, start_index)

    # ── Iterar en lotes ───────────────────────────────────────────────────────
    batches = _chunk(pending_urls, batch_size)

    for batch_offset, batch in enumerate(batches):
        global_batch_n = start_batch_n + batch_offset + 1  # 1-indexed para mostrar
        global_start   = start_index + batch_offset * batch_size

        progress.set_batch(global_batch_n, global_start)

        # Rotación de UA
        if ua_rotate_every > 0 and batch_offset > 0 and batch_offset % ua_rotate_every == 0:
            _rotate_session_ua(session_obj, cfg)

        # Aviso de VPN
        if global_batch_n >= next_vpn_reminder:
            _print_vpn_reminder(global_batch_n, total_batches)
            vpn_remind_interval = random.randint(*vpn_every_range)
            next_vpn_reminder   = global_batch_n + vpn_remind_interval

        sep = "─" * 52
        completed_so_far = len(ok_urls) + len(failed_urls)
        print()
        print(_c("96;1", f"  {sep}"))
        print(_c("97;1", f"  LOTE {global_batch_n}/{total_batches}  —  "
                          f"{completed_so_far}/{total_urls} URLs procesadas"))
        print(_c("96;1", f"  {sep}"))

        cf_blocked = False

        for i, url in enumerate(batch):
            global_i = global_start + i + 1  # posición global 1-indexed

            # Si ya estaba completada (reanudación parcial dentro del lote)
            if url in progress.completed_urls:
                print(_c("90", f"  [{global_i}/{total_urls}] Ya descargada, saltando: {url}"))
                ok_urls.append(url)
                continue

            print()
            print(_c("90",   f"  [{global_i}/{total_urls}] ") + _c("96", url))

            try:
                success = download_fn(url, output_path, conv_format, cookies)

                if success:
                    ok_urls.append(url)
                    progress.mark_completed(url)
                    history.add(url)
                else:
                    # Verificar si el fallo fue por Cloudflare
                    cf_blocked = _check_last_response_cf()
                    if cf_blocked:
                        progress.mark_failed(url)
                        failed_urls.append(url)
                        break
                    else:
                        failed_urls.append(url)
                        progress.mark_failed(url)

            except _CloudflareException:
                cf_blocked = True
                progress.mark_failed(url)
                failed_urls.append(url)
                break
            except Exception as e:
                print(_c("91;1", f"  [!] Error: {e}"))
                progress.mark_failed(url)
                failed_urls.append(url)

            # Delay entre descargas (salvo la última del lote)
            if i < len(batch) - 1 and not cf_blocked:
                delay = random.randint(*dl_delay_range)
                print(_c("90", f"  ⏳ Pausa {delay}s antes de la siguiente..."))
                time.sleep(delay)

        # ── Bloqueo Cloudflare: esperar y reanudar ─────────────────────────
        if cf_blocked:
            handle_cloudflare_block(cfg)
            # Reanudar en el mismo lote (el progress ya tiene lo completado)
            continue

        # ── Pausa entre lotes (no tras el último) ──────────────────────────
        if batch_offset < len(batches) - 1:
            lot_delay = random.randint(*lot_delay_range)
            lot_mins  = lot_delay // 60
            lot_secs  = lot_delay % 60
            print()
            print(_c("90", f"  {'─' * 52}"))
            print(_c("93", f"  ⏸  Lote {global_batch_n} completado. "
                            f"Pausa de {lot_mins}m {lot_secs}s antes del siguiente..."))
            _countdown(lot_delay)

    # ── Resumen final ─────────────────────────────────────────────────────────
    _print_batch_summary(ok_urls, failed_urls)
    progress.clear()

    return {"ok": ok_urls, "failed": failed_urls}


# ══════════════════════════════════════════════════════════════════════════════
# Helpers internos
# ══════════════════════════════════════════════════════════════════════════════

class _CloudflareException(Exception):
    pass


_last_cf_flag = False   # bandera simple para comunicar CF entre capas


def signal_cloudflare():
    """Llamar desde el DownloadEngine cuando detecta un bloqueo CF."""
    global _last_cf_flag
    _last_cf_flag = True


def _check_last_response_cf() -> bool:
    global _last_cf_flag
    flag = _last_cf_flag
    _last_cf_flag = False
    return flag


def _chunk(lst: list, n: int) -> list[list]:
    return [lst[i:i + n] for i in range(0, len(lst), n)]


def _rotate_session_ua(session_obj, cfg: dict):
    """Cambia el User-Agent de la sesión si se pasa un objeto de sesión."""
    from utils.config import rotate_user_agent
    new_ua = rotate_user_agent()
    if session_obj is not None:
        try:
            session_obj.headers.update({"User-Agent": new_ua})
        except Exception:
            pass
    print(_c("90", f"  [UA] User-Agent rotado → {new_ua[:60]}..."))


def _print_deep_mode_header(total: int, batches: int, batch_size: int, resume_from: int):
    sep = "═" * 52
    print()
    print(_c("96;1", f"  {sep}"))
    print(_c("97;1",  "  🚀  MODO DESCARGA PROFUNDA ACTIVADO"))
    print(_c("96;1", f"  {sep}"))
    print(_c("97",   f"  Total URLs   : {total}"))
    print(_c("97",   f"  Tamaño lote  : {batch_size} URLs"))
    print(_c("97",   f"  Lotes totales: {batches}"))
    if resume_from > 0:
        print(_c("93",  f"  Reanudando desde URL #{resume_from + 1}"))
    print(_c("90",    "  Delays aleatorios activos — protección anti-ban"))
    print(_c("96;1", f"  {sep}\n"))


def _print_vpn_reminder(current_batch: int, total_batches: int):
    sep = "═" * 52
    print()
    print(_c("93;1", f"  {sep}"))
    print(_c("93;1",  "  🌐  SUGERENCIA: CAMBIO DE IP / VPN"))
    print(_c("97",   f"  Lote actual: {current_batch} / {total_batches}"))
    print(_c("97",    "  Para reducir el riesgo de bloqueo, considera:"))
    print(_c("90",    "    • Cambiar de servidor VPN"))
    print(_c("90",    "    • Esperar unos minutos antes de continuar"))
    print(_c("90",    "    • Usar una conexión diferente (datos móviles / WiFi)"))
    print(_c("93;1", f"  {sep}"))
    print()
    _ask(_c("90", "  Pulsa Enter para continuar con el siguiente lote..."))


def _print_batch_summary(ok: list, failed: list):
    sep = "─" * 52
    print()
    print(_c("90",   f"  {sep}"))
    print(_c("97;1",  "  RESUMEN DEL LOTE"))
    print(_c("92;1",  f"  ✓ Completados : {len(ok)}"))
    if failed:
        print(_c("91;1", f"  ✗ Fallidos    : {len(failed)}"))
        for u in failed:
            print(_c("91", f"    - {u}"))
    print(_c("90", f"  {sep}\n"))