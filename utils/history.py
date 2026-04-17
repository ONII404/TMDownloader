# /utils/history.py
import datetime as _dt
import os

class HistoryManager:
    def __init__(self, file_path=".tmohentai_history.txt"):
        # Lo guardamos en la carpeta del script
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.file_path = os.path.join(base_dir, "..", file_path)

    def add(self, url: str):
        try:
            ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(f"[{ts}]  {url}\n")
        except Exception:
            pass

    def get_last(self, count=50):
        if not os.path.exists(self.file_path):
            return []
        with open(self.file_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
            return lines[-count:]