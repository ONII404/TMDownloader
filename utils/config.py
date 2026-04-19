# /utils/config.py
"""
Detecta la plataforma y gestiona toda la configuración del programa.
Persiste en .tmo_config.json junto al script.
"""
import sys
import os
import json
import random
from pathlib import Path

_CONFIG_FILE = Path(__file__).parent.parent / ".tmo_config.json"

# ── User-Agents predeterminados ───────────────────────────────────────────────
_USER_AGENTS = [
    # Chrome Android
    "Mozilla/5.0 (Linux; Android 13; Poco X6 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Samsung Galaxy S24) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 12; Redmi Note 11) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36",
    # Chrome Desktop
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Firefox Desktop
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

# ── Defaults completos ────────────────────────────────────────────────────────
_DEFAULTS = {
    # Salida
    "last_output": None,

    # Modo profundo
    "deep_mode_threshold":      10,     # URLs para activar modo profundo
    "batch_size":               25,     # URLs por lote
    "delay_between_downloads":  [5, 9], # segundos [min, max]
    "delay_between_batches":    [480, 900],  # segundos [min, max]  (8-15 min)
    "vpn_remind_every":         [4, 7], # cada N lotes [min, max]

    # Cloudflare
    "cf_wait_seconds":          [7200, 14400],  # 2-4 horas [min, max]

    # User-Agent
    "user_agent":               None,   # None = rotar automáticamente
    "ua_rotate_every_batches":  3,      # cambiar UA cada N lotes (0 = no rotar)
}


# ── Plataforma ────────────────────────────────────────────────────────────────

def _detect_platform() -> str:
    if sys.platform == "win32":
        return "windows"
    home = os.environ.get("HOME", "")
    if "com.termux" in home or os.path.exists("/data/data/com.termux"):
        return "android"
    return "linux"


def default_output_path() -> str:
    platform = _detect_platform()
    if platform == "android":
        return "/storage/emulated/0/Download/Manga"
    elif platform == "windows":
        return str(Path.home() / "Downloads" / "Manga")
    else:
        return str(Path.home() / "Manga")


# ── I/O de configuración ─────────────────────────────────────────────────────

def load_config() -> dict:
    if _CONFIG_FILE.exists():
        try:
            data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
            # Completar claves que pudieran faltar en configs viejos
            for k, v in _DEFAULTS.items():
                data.setdefault(k, v)
            return data
        except Exception:
            pass
    cfg = dict(_DEFAULTS)
    cfg["last_output"] = default_output_path()
    return cfg


def save_config(data: dict):
    try:
        current = load_config()
        current.update(data)
        _CONFIG_FILE.write_text(
            json.dumps(current, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def get_output_path() -> str:
    cfg = load_config()
    return cfg.get("last_output") or default_output_path()


# ── User-Agent ────────────────────────────────────────────────────────────────

def get_user_agent(cfg: dict | None = None) -> str:
    """Retorna el UA configurado o uno aleatorio de la lista."""
    if cfg is None:
        cfg = load_config()
    ua = cfg.get("user_agent")
    if ua:
        return ua
    return random.choice(_USER_AGENTS)


def rotate_user_agent() -> str:
    """Elige un UA aleatorio diferente al guardado actualmente y lo retorna
    (no lo persiste; la rotación es por sesión)."""
    return random.choice(_USER_AGENTS)


def list_user_agents() -> list[str]:
    return list(_USER_AGENTS)