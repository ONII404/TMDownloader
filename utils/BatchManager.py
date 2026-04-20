# /utils/BatchManager.py
"""
Gestión de descargas en lote con dos modos:
  - Normal   : ≤ threshold URLs, comportamiento original.
  - Profundo : > threshold URLs, lotes de N, reanudación segura,
               detección Cloudflare, avisos VPN, rotación UA.

Fuente de verdad para "qué saltar":
  skip_set = downloads_history.txt  ∪  failed_downloads.txt
  Una URL se omite si ya tuvo éxito O si ya falló en sesiones anteriores.
  Para reintentar fallos: borrar failed_downloads.txt o usar opción del menú.
"""
import time
import random
from pathlib import Path

from utils.ui      import _c, _ask
from utils.config  import load_config
from utils.history import HistoryManager, FailedManager, ProgressState

BATCH_FILE              = Path(__file__).parent.parent / "lista.txt"
DELAY_BETWEEN_DOWNLOADS = 5

_TEMPLATE = """\
# TMD - Lista de descargas en lote
# Una URL por línea. Las líneas que empiezan con # son comentarios.
#
# Ejemplos:
# https://tmohentai.com/contents/69b6fd0b4a6fa
# https://lectorhentai.com/manga/24514/loca-por-ti
"""

_CF_STATUS_CODES = {429, 403, 503, 1015}
_CF_KEYWORDS     = ["cloudflare", "cf-ray", "challenge", "just a moment", "ddos"]


# ══════════════════════════════════════════════════════════════════════════════
# Helpers de lista
# ══════════════════════════════════════════════════════════════════════════════

def ensure_batch_file() -> bool:
    if BATCH_FILE.exists():
        return True
    BATCH_FILE.write_text(_TEMPLATE, encoding="utf-8")
    print(_c("93;1", "\n  [!] No existía lista.txt — se creó la plantilla en:"))
    print(_c("90",   f"      {BATCH_FILE}"))
    print(_c("90",    "      Añade tus URLs y vuelve a elegir esta opción.\n"))
    return False


def load_urls() -> list[str]:
    seen, urls = set(), []
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
# Cloudflare
# ══════════════════════════════════════════════════════════════════════════════

def is_cloudflare_block(status_code: int, response_text: str = "") -> bool:
    if status_code in _CF_STATUS_CODES:
        return True
    return any(kw in response_text.lower() for kw in _CF_KEYWORDS)


def handle_cloudflare_block(cfg: dict):
    wait_range = cfg.get("cf_wait_seconds", [7200, 14400])
    wait_secs  = random.randint(wait_range[0], wait_range[1])
    wait_hrs   = wait_secs // 3600
    wait_mins  = (wait_secs % 3600) // 60
    sep = "═" * 52
    print()
    print(_c("91;1", f"  {sep}"))
    print(_c("91;1",  "  ⛔  BLOQUEO DE CLOUDFLARE DETECTADO"))
    print(_c("91;1", f"  {sep}"))
    print(_c("97",    "  Cloudflare ha bloqueado las peticiones (403/429/1015)."))
    print(_c("97",    "  El script esperará automáticamente antes de continuar."))
    print()
    print(_c("93;1", f"  ⏳ Esperando {wait_hrs}h {wait_mins}m ({wait_secs}s)..."))
    print(_c("90",    "  Puedes dejar el script corriendo o cerrarlo."))
    print(_c("90",    "  Al reanudar, continuará desde la última URL completada."))
    print(_c("91;1", f"  {sep}\n"))
    _countdown(wait_secs)


def _countdown(seconds: int):
    for remaining in range(seconds, 0, -1):
        h = remaining // 3600
        m = (remaining % 3600) // 60
        s = remaining % 60
        print(f"\r  {_c('90', f'⏳ Reanudando en {h:02d}:{m:02d}:{s:02d}...')}",
              end="", flush=True)
        time.sleep(1)
    print()


# ══════════════════════════════════════════════════════════════════════════════
# Modo Normal
# ══════════════════════════════════════════════════════════════════════════════

def run_batch(urls, download_fn, output_path, conv_format, cookies,
              delay=DELAY_BETWEEN_DOWNLOADS) -> dict:
    total, ok, failed = len(urls), [], []
    print(_c("97;1", f"\n  DESCARGA EN LOTE — {total} manga(s)\n"))
    for i, url in enumerate(urls, 1):
        print(_c("90",   f"  {'─' * 50}"))
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

def run_deep_batch(urls, download_fn, output_path, conv_format, cookies,
                   session_obj=None) -> dict:
    """
    Reanudación:
      skip_set = done_set ∪ failed_set  → se salta cualquier URL procesada
      start_index = primer índice de urls[] no presente en skip_set

    El last_index del JSON solo sirve como pista para acelerar el scan
    (empezamos desde ese punto, no desde 0), pero el scan siempre recorre
    hacia atrás un lote por si el lote quedó a medias. Si el JSON tiene un
    índice desactualizado (bug de sesión anterior), el scan simplemente
    encuentra la posición correcta igualmente porque compara contra
    skip_set (la fuente de verdad real), no contra el índice guardado.
    """
    cfg = load_config()
    batch_size      = cfg.get("batch_size", 25)
    dl_delay_range  = cfg.get("delay_between_downloads", [5, 9])
    lot_delay_range = cfg.get("delay_between_batches", [480, 900])
    vpn_every_range = cfg.get("vpn_remind_every", [4, 7])
    ua_rotate_every = cfg.get("ua_rotate_every_batches", 3)

    history  = HistoryManager()
    failed_m = FailedManager()
    progress = ProgressState()

    total_urls = len(urls)

    # ── Construir skip_set: todo lo que NO hay que descargar ──────────────────
    done_set   = history._get_done_set()
    failed_set = failed_m._get_failed_set()
    skip_set   = done_set | failed_set      # unión: éxitos + fallos previos

    done_count   = len(done_set)
    failed_count = len(failed_set)
    skip_count   = len(skip_set)

    # ── Calcular start_index usando el historial como fuente de verdad ─────────
    #
    # Pista del JSON: empezar el scan desde (last_index - batch_size) para
    # cubrir el lote que pudo quedar a medias. Si la pista es 0 o negativa
    # (JSON nuevo o desactualizado), el scan empieza desde 0 — costo O(n)
    # solo la primera vez, después la pista acelera el proceso.
    #
    start_index = 0
    can_resume  = progress.can_resume(BATCH_FILE) and skip_count > 0

    if can_resume:
        hint = max(0, progress.last_index - batch_size)
        # Escanear hacia adelante desde la pista
        start_index = total_urls  # asumir todo listo hasta demostrar lo contrario
        for i in range(hint, total_urls):
            if urls[i] not in skip_set:
                start_index = i
                break
        # Si la pista apuntaba demasiado lejos (bug de sesión anterior),
        # hacer scan completo desde 0 para no perdernos nada
        if start_index == total_urls and hint > 0:
            for i in range(0, total_urls):
                if urls[i] not in skip_set:
                    start_index = i
                    break

    # ── Banner de reanudación ─────────────────────────────────────────────────
    if can_resume and start_index < total_urls:
        sep = "═" * 52
        print()
        print(_c("93;1", f"  {sep}"))
        print(_c("93;1",  "  🔄  REANUDANDO SESIÓN ANTERIOR"))
        print(_c("97",   f"  Descargadas OK : {done_count} / {total_urls}"))
        if failed_count:
            print(_c("91",  f"  Fallos previos : {failed_count} (se omitirán)"))
        print(_c("97",   f"  Continuando desde URL #{start_index + 1}"))
        print(_c("93;1", f"  {sep}\n"))
        confirm = _ask(_c("93;1", "  ¿Reanudar desde donde se quedó? [S/n] > "))
        if confirm.lower() == "n":
            progress.init_session(urls, BATCH_FILE)
            start_index  = 0
            skip_set     = set()
            done_count   = 0
            failed_count = 0
            skip_count   = 0
    else:
        progress.init_session(urls, BATCH_FILE)
        start_index = 0

    if start_index >= total_urls:
        print(_c("92;1", "\n  ✓  Todas las URLs ya están procesadas."))
        if failed_count:
            print(_c("91", f"  {failed_count} URLs fallidas están en failed_downloads.txt"))
            print(_c("90",  "  Para reintentarlas: borra ese archivo y vuelve a ejecutar."))
        progress.clear()
        return {"ok": done_count, "failed": failed_count}

    # ── Preparar contadores ───────────────────────────────────────────────────
    total_batches = (total_urls + batch_size - 1) // batch_size
    start_batch_n = start_index // batch_size

    session_ok     = 0
    session_failed = 0

    vpn_remind_interval = random.randint(*vpn_every_range)
    next_vpn_reminder   = start_batch_n + vpn_remind_interval

    _print_deep_mode_header(total_urls, total_batches, batch_size,
                             start_index, done_count, failed_count)

    # ── Iterar en lotes ───────────────────────────────────────────────────────
    pending_urls = urls[start_index:]
    batches      = _chunk(pending_urls, batch_size)

    for batch_offset, batch in enumerate(batches):
        global_batch_n = start_batch_n + batch_offset + 1
        global_start   = start_index + batch_offset * batch_size

        progress.set_position(global_start, global_batch_n)

        if ua_rotate_every > 0 and batch_offset > 0 and batch_offset % ua_rotate_every == 0:
            _rotate_session_ua(session_obj, cfg)

        if global_batch_n >= next_vpn_reminder:
            _print_vpn_reminder(global_batch_n, total_batches)
            vpn_remind_interval = random.randint(*vpn_every_range)
            next_vpn_reminder   = global_batch_n + vpn_remind_interval

        total_processed = done_count + session_ok + session_failed + failed_count
        sep = "─" * 52
        print()
        print(_c("96;1", f"  {sep}"))
        print(_c("97;1", f"  LOTE {global_batch_n}/{total_batches}  —  "
                          f"{total_processed}/{total_urls} URLs procesadas"))
        print(_c("96;1", f"  {sep}"))

        cf_blocked          = False
        batch_had_downloads = False

        for i, url in enumerate(batch):
            global_i = global_start + i + 1

            # Saltar silenciosamente URLs ya procesadas (éxito o fallo previo)
            if url in skip_set:
                continue

            batch_had_downloads = True
            print()
            print(_c("90", f"  [{global_i}/{total_urls}] ") + _c("96", url))

            try:
                success = download_fn(url, output_path, conv_format, cookies)

                if success:
                    history.add(url)        # append a downloads_history.txt
                    done_set.add(url)
                    skip_set.add(url)
                    done_count  += 1
                    session_ok  += 1
                    progress.set_position(global_i - 1, global_batch_n)
                else:
                    cf_blocked = _check_last_response_cf()
                    failed_m.add(url)       # append a failed_downloads.txt
                    failed_set.add(url)
                    skip_set.add(url)
                    failed_count  += 1
                    session_failed += 1
                    if cf_blocked:
                        break

            except _CloudflareException:
                cf_blocked     = True
                failed_m.add(url)
                failed_set.add(url)
                skip_set.add(url)
                failed_count  += 1
                session_failed += 1
                break
            except Exception as e:
                print(_c("91;1", f"  [!] Error: {e}"))
                failed_m.add(url)
                failed_set.add(url)
                skip_set.add(url)
                failed_count  += 1
                session_failed += 1

            if i < len(batch) - 1 and not cf_blocked:
                delay = random.randint(*dl_delay_range)
                print(_c("90", f"  ⏳ Pausa {delay}s antes de la siguiente..."))
                time.sleep(delay)

        if cf_blocked:
            handle_cloudflare_block(cfg)
            continue

        if batch_offset < len(batches) - 1 and batch_had_downloads:
            lot_delay = random.randint(*lot_delay_range)
            lot_mins  = lot_delay // 60
            lot_secs  = lot_delay % 60
            print()
            print(_c("90", f"  {'─' * 52}"))
            print(_c("93", f"  ⏸  Lote {global_batch_n} completado. "
                            f"Pausa de {lot_mins}m {lot_secs}s antes del siguiente..."))
            _countdown(lot_delay)

    # ── Resumen final ─────────────────────────────────────────────────────────
    print()
    sep = "─" * 52
    print(_c("90",   f"  {sep}"))
    print(_c("97;1",  "  RESUMEN DE SESIÓN"))
    print(_c("92;1",  f"  ✓ Descargadas esta sesión  : {session_ok}"))
    print(_c("92;1",  f"  ✓ Total acumulado (éxitos) : {done_count} / {total_urls}"))
    if session_failed:
        print(_c("91;1", f"  ✗ Fallos esta sesión       : {session_failed}"))
    if failed_count:
        print(_c("91",   f"  ✗ Total fallos acumulados  : {failed_count}"))
        print(_c("90",    "    → Guardados en failed_downloads.txt"))
        print(_c("90",    "    → Borra ese archivo para reintentarlos"))
    print(_c("90", f"  {sep}\n"))

    progress.clear()
    return {"ok": session_ok, "failed": session_failed}


# ══════════════════════════════════════════════════════════════════════════════
# Internos
# ══════════════════════════════════════════════════════════════════════════════

class _CloudflareException(Exception):
    pass

_last_cf_flag = False

def signal_cloudflare():
    global _last_cf_flag
    _last_cf_flag = True

def _check_last_response_cf() -> bool:
    global _last_cf_flag
    flag = _last_cf_flag
    _last_cf_flag = False
    return flag

def _chunk(lst, n):
    return [lst[i:i + n] for i in range(0, len(lst), n)]

def _rotate_session_ua(session_obj, cfg):
    from utils.config import rotate_user_agent
    new_ua = rotate_user_agent()
    if session_obj is not None:
        try:
            session_obj.headers.update({"User-Agent": new_ua})
        except Exception:
            pass
    print(_c("90", f"  [UA] User-Agent rotado → {new_ua[:60]}..."))

def _print_deep_mode_header(total, batches, batch_size, resume_from,
                             done_count, failed_count):
    pending = total - done_count - failed_count
    sep = "═" * 52
    print()
    print(_c("96;1", f"  {sep}"))
    print(_c("97;1",  "  🚀  MODO DESCARGA PROFUNDA ACTIVADO"))
    print(_c("96;1", f"  {sep}"))
    print(_c("97",   f"  Total URLs      : {total}"))
    print(_c("92",   f"  Ya descargadas  : {done_count}"))
    if failed_count:
        print(_c("91",  f"  Fallos previos  : {failed_count} (se omitirán)"))
    print(_c("97",   f"  Pendientes      : {pending}"))
    print(_c("97",   f"  Tamaño lote     : {batch_size} URLs"))
    print(_c("97",   f"  Lotes totales   : {batches}"))
    if resume_from > 0:
        print(_c("93",  f"  Reanudando desde URL #{resume_from + 1}"))
    print(_c("90",    "  Delays aleatorios activos — protección anti-ban"))
    print(_c("96;1", f"  {sep}\n"))

def _print_vpn_reminder(current_batch, total_batches):
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

def _print_batch_summary(ok, failed):
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