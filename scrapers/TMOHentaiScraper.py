# /scrapers/TMOHentaiScraper.py
from scrapers.BaseScraper import BaseScraper
import re
import requests

class TMOHentaiScraper(BaseScraper):
    def __init__(self):
        self.cdn_hosts = [
            "cache1.tmohentai.com",
            "cache2.tmohentai.com",
            "cache3.tmohentai.com",
            "cache4.tmohentai.com",
        ]
        self.extensions = [".webp", ".jpg", ".jpeg", ".png"]

    def matches(self, url: str) -> bool:
        return "tmohentai.com" in url or (len(url) == 13 and url.isalnum())

    def extract_id(self, url: str) -> str:
        m = re.search(r"/(?:contents|reader)/([a-zA-Z0-9]+)", url)
        return m.group(1) if m else url

    def _head_ok(self, session, url: str, referer: str) -> bool:
        """
        HEAD request con manejo de errores.
        Usa requests directamente para evitar el overhead de cloudscraper
        en peticiones de probing (no necesitan bypass de JS).
        """
        headers = {"Referer": referer}
        # Intentamos primero con la sesión original (tiene las cookies/headers)
        # y como fallback usamos requests puro si hay error de red.
        for verify in [True, False]:
            try:
                r = session.head(url, headers=headers, timeout=10, verify=verify)
                return r.status_code == 200
            except requests.exceptions.ConnectionError:
                # DNS fallo o conexión rechazada — este host/URL no existe
                return False
            except requests.exceptions.Timeout:
                # Timeout en HEAD = probablemente no existe, continuar
                return False
            except Exception:
                continue
        return False

    def get_image_tasks(self, session, cid: str, dest_dir) -> list:
        """
        Hace probing HEAD para descubrir qué imágenes existen,
        y retorna la lista de tareas (url, dest_path, referer) para el Engine.
        """
        tasks = []
        referer = f"https://tmohentai.com/reader/{cid}/cascade"
        fails = 0

        print(f"  Patrón CDN: https://cache1.tmohentai.com/contents/{cid}/000.webp")

        for i in range(1000):
            found = False
            host = self.cdn_hosts[i % len(self.cdn_hosts)]

            for ext in self.extensions:
                img_url = f"https://{host}/contents/{cid}/{i:03d}{ext}"
                if self._head_ok(session, img_url, referer):
                    dest_file = dest_dir / f"{i:03d}{ext}"
                    tasks.append((img_url, dest_file, referer))
                    found = True
                    break

            if found:
                fails = 0
                print(f"\r  Encontradas: {len(tasks)} imagen(s)...", end="", flush=True)
            else:
                fails += 1

            if fails >= 3:
                break

        print()  # salto de línea tras el conteo
        return tasks

    def get_image_urls(self, session, cid: str):
        """Generador de URLs (compatibilidad con BaseScraper legacy)."""
        referer = f"https://tmohentai.com/reader/{cid}/cascade"
        fails = 0
        for i in range(1000):
            found = False
            host = self.cdn_hosts[i % len(self.cdn_hosts)]
            for ext in self.extensions:
                img_url = f"https://{host}/contents/{cid}/{i:03d}{ext}"
                if self._head_ok(session, img_url, referer):
                    yield img_url
                    found = True
                    break
            if found:
                fails = 0
            else:
                fails += 1
            if fails >= 3:
                break