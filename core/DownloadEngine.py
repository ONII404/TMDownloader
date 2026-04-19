# /core/DownloadEngine.py
"""
Motor de descarga paralela con barra de progreso visual.
"""
import concurrent.futures
import sys
import time


class DownloadEngine:

    def __init__(self, session, max_workers: int = 5):
        self.session     = session
        self.max_workers = max_workers

    # ── Descarga de una imagen ────────────────────────────────────────────────

    def download_image(self, url: str, dest_path, referer: str):
        """
        Descarga una sola imagen.
        Retorna (True, url) si tuvo éxito, (False, url) si falló.
        """
        headers = {"Referer": referer}
        for verify in (True, False):
            try:
                r = self.session.get(
                    url, headers=headers, timeout=20,
                    stream=True, verify=verify
                )
                if r.status_code == 200:
                    with open(dest_path, "wb") as f:
                        for chunk in r.iter_content(8192):
                            f.write(chunk)
                    return True, url
                break   # 4xx/5xx: no reintentar con SSL desactivado
            except Exception:
                continue
        return False, url

    # ── Descarga de un manga completo ─────────────────────────────────────────

    def download_manga(self, image_tasks: list, title: str = "") -> bool:
        """
        Descarga todas las imágenes en paralelo con barra de progreso.

        image_tasks : lista de tuplas (url, dest_path, referer)
        title       : nombre del manga/capítulo para mostrar en pantalla

        Retorna True si todas las imágenes se descargaron correctamente.
        """
        total       = len(image_tasks)
        done        = 0
        failed_urls = []
        start_time  = time.time()

        # Encabezado de la barra
        _print_progress(done, total, failed=0, title=title, elapsed=0)

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            futures = {
                executor.submit(self.download_image, *task): task
                for task in image_tasks
            }

            for future in concurrent.futures.as_completed(futures):
                success, url = future.result()
                done += 1
                elapsed = time.time() - start_time

                if not success:
                    failed_urls.append(url)

                _print_progress(
                    done, total,
                    failed=len(failed_urls),
                    title=title,
                    elapsed=elapsed,
                )

        # Salto de línea tras la barra
        print()

        if failed_urls:
            _c = _ansi
            print(_c("91;1", f"\n  [!] {len(failed_urls)} imagen(s) no descargada(s):"))
            for u in failed_urls:
                print(_c("91", f"      - {u}"))

        return len(failed_urls) == 0


# ── Helpers de UI ─────────────────────────────────────────────────────────────

_BAR_WIDTH = 28   # caracteres de la barra interna


def _ansi(code: str, text: str) -> str:
    """Aplica color ANSI si el terminal lo soporta."""
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def _print_progress(
    done: int, total: int,
    failed: int,
    title: str,
    elapsed: float,
) -> None:
    """
    Imprime una línea de progreso con barra visual usando \\r.

    Ejemplo:
      Descargando ░░░░░░░░░░░░░░░░░░░░░░░░░░░░  0 / 26  0.0s
      Descargando ████████████████░░░░░░░░░░░░ 16 / 26  3.1s
      Descargando ████████████████████████████ 26 / 26  5.8s  ✓
    """
    c = _ansi

    pct     = done / total if total else 0
    filled  = int(_BAR_WIDTH * pct)
    bar     = "█" * filled + "░" * (_BAR_WIDTH - filled)

    # Color de la barra: verde si terminó, amarillo si va, rojo si hay fallos
    if done == total:
        bar_color = "92" if failed == 0 else "93"
    else:
        bar_color = "91" if failed else "96"

    bar_str    = c(bar_color, bar)
    count_str  = c("97", f"{done:>3} / {total}")
    time_str   = c("90", f"{elapsed:>5.1f}s")

    fail_str = ""
    if failed:
        fail_str = c("91;1", f"  ✗ {failed} fallo(s)")

    end_str = ""
    if done == total:
        end_str = c("92;1", "  ✓") if not failed else c("93;1", "  ⚠")

    line = f"  {bar_str}  {count_str}  {time_str}{fail_str}{end_str}"
    print(f"\r{line}", end="", flush=True)