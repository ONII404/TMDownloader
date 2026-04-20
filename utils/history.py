# /utils/history.py
"""
Historial de descargas y estado de progreso para reanudación segura.

Archivos:
  downloads_history.txt  — fuente de verdad de URLs descargadas con éxito
  failed_downloads.txt   — fuente de verdad de URLs que fallaron definitivamente
  .tmd_progress.json     — solo metadatos de posición (hash + last_index)

Por qué archivos separados para ok/failed:
  Ambos son append-only y nunca se reescriben enteros, por lo que son seguros
  ante cierres abruptos. El JSON es mínimo (3 campos) y raramente se escribe.

Fuente de verdad para "qué saltar":
  skip_set = done_set ∪ failed_set
  Una URL se salta si ya se descargó O si ya falló en una sesión anterior.

Compatibilidad: si existe .tmohentai_history.txt se migra automáticamente.
"""
import datetime as _dt
import json
import os
from pathlib import Path

_ROOT = Path(__file__).parent.parent

_HISTORY_FILE  = _ROOT / "downloads_history.txt"
_FAILED_FILE   = _ROOT / "failed_downloads.txt"
_LEGACY_FILE   = _ROOT / ".tmohentai_history.txt"
_PROGRESS_FILE = _ROOT / ".tmd_progress.json"


# ══════════════════════════════════════════════════════════════════════════════
# HistoryManager  —  fuente de verdad de descargas completadas
# ══════════════════════════════════════════════════════════════════════════════

class HistoryManager:

    def __init__(self):
        self.file_path = _HISTORY_FILE
        self._migrate_legacy()
        self._done: set[str] | None = None

    # ── Migración ─────────────────────────────────────────────────────────────

    def _migrate_legacy(self):
        if not _LEGACY_FILE.exists():
            return
        try:
            legacy_lines = _LEGACY_FILE.read_text(encoding="utf-8").splitlines()
            existing = set()
            if self.file_path.exists():
                existing = set(self.file_path.read_text(encoding="utf-8").splitlines())
            new_lines = [l for l in legacy_lines if l.strip() and l not in existing]
            if new_lines:
                with open(self.file_path, "a", encoding="utf-8") as f:
                    f.write("\n".join(new_lines) + "\n")
            _LEGACY_FILE.unlink()
            print(f"  [i] Historial migrado de {_LEGACY_FILE.name} → {_HISTORY_FILE.name}")
        except Exception:
            pass

    # ── API pública ───────────────────────────────────────────────────────────

    def add(self, url: str):
        """Añade URL al historial de éxitos (append-only)."""
        try:
            ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(f"[{ts}]  {url}\n")
            if self._done is not None:
                self._done.add(url)
        except Exception:
            pass

    def get_last(self, count: int = 50) -> list[str]:
        if not self.file_path.exists():
            return []
        with open(self.file_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        return lines[-count:]

    def contains(self, url: str) -> bool:
        return url in self._get_done_set()

    def _get_done_set(self) -> set[str]:
        if self._done is None:
            self._done = _load_url_set(_HISTORY_FILE)
        return self._done

    def count_done(self) -> int:
        return len(self._get_done_set())


# ══════════════════════════════════════════════════════════════════════════════
# FailedManager  —  fuente de verdad de URLs que fallaron definitivamente
# ══════════════════════════════════════════════════════════════════════════════

class FailedManager:

    def __init__(self):
        self.file_path = _FAILED_FILE
        self._failed: set[str] | None = None

    def add(self, url: str):
        """Registra una URL fallida (append-only)."""
        try:
            ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(f"[{ts}]  {url}\n")
            if self._failed is not None:
                self._failed.add(url)
        except Exception:
            pass

    def contains(self, url: str) -> bool:
        return url in self._get_failed_set()

    def _get_failed_set(self) -> set[str]:
        if self._failed is None:
            self._failed = _load_url_set(_FAILED_FILE)
        return self._failed

    def count_failed(self) -> int:
        return len(self._get_failed_set())

    def get_all(self) -> list[str]:
        return sorted(self._get_failed_set())

    def retry_all(self):
        """Borra el archivo de fallos para reintentar todo en la próxima sesión."""
        try:
            if self.file_path.exists():
                self.file_path.unlink()
            self._failed = None
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# ProgressState  —  solo metadatos de posición
# ══════════════════════════════════════════════════════════════════════════════

class ProgressState:
    """
    Persiste metadatos mínimos de la sesión para poder reanudar.

    Estructura de .tmd_progress.json:
    {
      "batch_file_hash": "abc123def456",
      "total_urls":      5448,
      "last_index":      573,      ← índice global del último ítem procesado
      "current_batch":   23,
      "timestamp":       "2024-06-01 14:32:00"
    }

    Las URLs completadas/fallidas se leen de sus archivos .txt correspondientes.
    """

    def __init__(self):
        self.file   = _PROGRESS_FILE
        self._state = self._load()

    def _load(self) -> dict:
        if self.file.exists():
            try:
                return json.loads(self.file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def save(self):
        try:
            self._state["timestamp"] = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.file.write_text(
                json.dumps(self._state, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def clear(self):
        try:
            if self.file.exists():
                self.file.unlink()
        except Exception:
            pass
        self._state = {}

    @staticmethod
    def hash_file(path: Path) -> str:
        import hashlib
        try:
            return hashlib.sha1(path.read_bytes()).hexdigest()[:12]
        except Exception:
            return ""

    def init_session(self, urls: list[str], batch_file: Path):
        self._state = {
            "batch_file_hash": self.hash_file(batch_file),
            "total_urls":      len(urls),
            "last_index":      -1,
            "current_batch":   0,
        }
        self.save()

    def can_resume(self, batch_file: Path) -> bool:
        if not self._state:
            return False
        return self._state.get("batch_file_hash", "") == self.hash_file(batch_file)

    def set_position(self, index: int, batch_num: int):
        self._state["last_index"]    = index
        self._state["current_batch"] = batch_num
        self.save()

    @property
    def last_index(self) -> int:
        return self._state.get("last_index", -1)

    @property
    def current_batch(self) -> int:
        return self._state.get("current_batch", 0)

    @property
    def total_urls(self) -> int:
        return self._state.get("total_urls", 0)

    def has_state(self) -> bool:
        return bool(self._state)


# ══════════════════════════════════════════════════════════════════════════════
# Helper interno compartido
# ══════════════════════════════════════════════════════════════════════════════

def _load_url_set(path: Path) -> set[str]:
    """
    Lee un archivo de historial (éxitos o fallos) y devuelve un set de URLs.
    Formato de línea: "[YYYY-MM-DD HH:MM:SS]  url"  o solo "url" (legado).
    """
    result = set()
    if not path.exists():
        return result
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if "]  " in line:
                    url = line.split("]  ", 1)[1].strip()
                else:
                    url = line
                if url:
                    result.add(url)
    except Exception:
        pass
    return result