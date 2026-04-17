# /utils/config.py
"""
Detecta la plataforma y sugiere la ruta de salida por defecto.
Persiste la última ruta usada en un archivo JSON junto al script.
"""
import sys
import os
import json
from pathlib import Path

_CONFIG_FILE = Path(__file__).parent.parent / ".tmo_config.json"


def _detect_platform() -> str:
    """Retorna 'android', 'windows' o 'linux'."""
    if sys.platform == "win32":
        return "windows"
    # En Termux/Android, el HOME suele ser /data/data/com.termux/...
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


def load_config() -> dict:
    if _CONFIG_FILE.exists():
        try:
            return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_config(data: dict):
    try:
        current = load_config()
        current.update(data)
        _CONFIG_FILE.write_text(
            json.dumps(current, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception:
        pass


def get_output_path() -> str:
    """Retorna la última ruta usada, o la ruta por defecto si es la primera vez."""
    cfg = load_config()
    return cfg.get("last_output", default_output_path())
