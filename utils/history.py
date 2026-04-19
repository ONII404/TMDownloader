# /utils/history.py
"""
Historial de descargas y estado de progreso para reanudación segura.

Archivos:
  downloads_history.txt  — registro legible de descargas completadas
  .tmd_progress.json     — estado del lote actual (para reanudar si se corta)

Compatibilidad: si existe el archivo antiguo (.tmohentai_history.txt),
se migra automáticamente a downloads_history.txt en la primera ejecución.
"""
import datetime as _dt
import json
import os
from pathlib import Path

_ROOT = Path(__file__).parent.parent

_HISTORY_FILE   = _ROOT / "downloads_history.txt"
_LEGACY_FILE    = _ROOT / ".tmohentai_history.txt"
_PROGRESS_FILE  = _ROOT / ".tmd_progress.json"


# ══════════════════════════════════════════════════════════════════════════════
# Historial de descargas
# ══════════════════════════════════════════════════════════════════════════════

class HistoryManager:

    def __init__(self):
        self.file_path = _HISTORY_FILE
        self._migrate_legacy()

    # ── Migración ─────────────────────────────────────────────────────────────

    def _migrate_legacy(self):
        """Si existe el historial viejo, lo fusiona en el nuevo y lo elimina."""
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
        try:
            ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(f"[{ts}]  {url}\n")
        except Exception:
            pass

    def get_last(self, count: int = 50) -> list[str]:
        if not self.file_path.exists():
            return []
        with open(self.file_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        return lines[-count:]

    def contains(self, url: str) -> bool:
        """Retorna True si la URL ya fue descargada anteriormente."""
        if not self.file_path.exists():
            return False
        with open(self.file_path, "r", encoding="utf-8") as f:
            return any(url in line for line in f)


# ══════════════════════════════════════════════════════════════════════════════
# Estado de progreso (reanudación segura)
# ══════════════════════════════════════════════════════════════════════════════

class ProgressState:
    """
    Persiste el estado del lote actual para reanudar si se interrumpe.

    Estructura de .tmd_progress.json:
    {
      "batch_file_hash": "<sha1 del lista.txt>",
      "total_urls":      5448,
      "completed_urls":  ["url1", "url2", ...],
      "failed_urls":     ["url3"],
      "current_batch":   12,
      "current_index":   300,
      "timestamp":       "2024-06-01 14:32:00"
    }
    """

    def __init__(self):
        self.file = _PROGRESS_FILE
        self._state = self._load()

    # ── Carga / guardado ──────────────────────────────────────────────────────

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
        """Elimina el estado guardado (lote terminado)."""
        try:
            if self.file.exists():
                self.file.unlink()
        except Exception:
            pass
        self._state = {}

    # ── Hash del archivo de lista ─────────────────────────────────────────────

    @staticmethod
    def hash_file(path: Path) -> str:
        import hashlib
        try:
            return hashlib.sha1(path.read_bytes()).hexdigest()[:12]
        except Exception:
            return ""

    # ── Inicialización de sesión ──────────────────────────────────────────────

    def init_session(self, urls: list[str], batch_file: Path):
        """Inicia una nueva sesión de descarga (borra estado anterior)."""
        self._state = {
            "batch_file_hash": self.hash_file(batch_file),
            "total_urls":      len(urls),
            "completed_urls":  [],
            "failed_urls":     [],
            "current_batch":   0,
            "current_index":   0,
        }
        self.save()

    def resume_session(self, urls: list[str], batch_file: Path) -> tuple[bool, int]:
        """
        Comprueba si hay un estado guardado compatible con la lista actual.
        Retorna (puede_reanudar, indice_desde_donde_continuar).
        """
        if not self._state:
            return False, 0

        saved_hash = self._state.get("batch_file_hash", "")
        curr_hash  = self.hash_file(batch_file)

        if saved_hash != curr_hash:
            return False, 0

        completed = set(self._state.get("completed_urls", []))
        # Encontrar el primer índice no completado
        for i, url in enumerate(urls):
            if url not in completed:
                return True, i

        return False, len(urls)  # Todo ya completado

    # ── Actualización de progreso ─────────────────────────────────────────────

    def mark_completed(self, url: str):
        self._state.setdefault("completed_urls", [])
        if url not in self._state["completed_urls"]:
            self._state["completed_urls"].append(url)
        self.save()

    def mark_failed(self, url: str):
        self._state.setdefault("failed_urls", [])
        if url not in self._state["failed_urls"]:
            self._state["failed_urls"].append(url)
        self.save()

    def set_batch(self, batch_num: int, global_index: int):
        self._state["current_batch"] = batch_num
        self._state["current_index"] = global_index
        self.save()

    # ── Getters ───────────────────────────────────────────────────────────────

    @property
    def completed_urls(self) -> set:
        return set(self._state.get("completed_urls", []))

    @property
    def failed_urls(self) -> list:
        return self._state.get("failed_urls", [])

    @property
    def current_batch(self) -> int:
        return self._state.get("current_batch", 0)

    @property
    def total_urls(self) -> int:
        return self._state.get("total_urls", 0)

    def has_state(self) -> bool:
        return bool(self._state)