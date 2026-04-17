# /scrapers/TMOHentaiScraper.py
from scrapers.BaseScraper import BaseScraper
import re
import requests


class TMOHentaiScraper(BaseScraper):

    _source_name = "TMOHentai"

    def __init__(self):
        self.cdn_hosts = [
            "cache1.tmohentai.com",
            "cache2.tmohentai.com",
            "cache3.tmohentai.com",
            "cache4.tmohentai.com",
        ]
        self.extensions = [".webp", ".jpg", ".jpeg", ".png"]

    # ── Obligatorios ────────────────────────────────────────────────────────

    def matches(self, url: str) -> bool:
        return "tmohentai.com" in url or (len(url) == 13 and url.isalnum())

    def extract_id(self, url: str) -> str:
        m = re.search(r"/(?:contents|reader)/([a-zA-Z0-9]+)", url)
        return m.group(1) if m else url

    def get_image_tasks(self, session, cid: str, dest_dir) -> list:
        """
        Hace probing HEAD para descubrir las imágenes disponibles en el CDN
        y retorna la lista de tareas para el DownloadEngine.
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

        print()
        return tasks

    # ── Metadata ────────────────────────────────────────────────────────────

    def get_metadata(self, session, cid: str) -> dict:
        """
        Intenta extraer metadata de la página del manga en tmohentai.com.
        Si falla o los campos no están, usa valores genéricos del método base.
        """
        meta = super().get_metadata(session, cid)   # base con fallbacks
        meta["Web"] = f"https://tmohentai.com/contents/{cid}"

        try:
            url  = f"https://tmohentai.com/contents/{cid}"
            resp = session.get(url, timeout=15)
            if resp.status_code != 200:
                return meta

            html = resp.text

            # Título (og:title o <title>)
            m = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html)
            if not m:
                m = re.search(r"<title>([^<]+)</title>", html)
            if m:
                title = m.group(1).strip().replace(" | TMOHentai", "").strip()
                meta["Title"]  = title
                meta["Series"] = title

            # Autor/artista
            m = re.search(r'(?:autor|artist)[^<]*<[^>]+>([^<]+)<', html, re.IGNORECASE)
            if m:
                meta["Writer"] = m.group(1).strip()

            # Tags / géneros
            tags = re.findall(r'<a[^>]+/tag/[^>]+>([^<]+)</a>', html)
            if tags:
                meta["Tags"]  = ", ".join(t.strip() for t in tags)
                meta["Genre"] = tags[0].strip() if tags else ""

            # Idioma
            if re.search(r'español|spanish', html, re.IGNORECASE):
                meta["LanguageISO"] = "es"
            elif re.search(r'english', html, re.IGNORECASE):
                meta["LanguageISO"] = "en"
            elif re.search(r'japanese', html, re.IGNORECASE):
                meta["LanguageISO"] = "ja"

        except Exception:
            pass  # Si falla el scraping de meta, usamos lo que ya hay

        return meta

    # ── Interno ─────────────────────────────────────────────────────────────

    def _head_ok(self, session, url: str, referer: str) -> bool:
        """HEAD request tolerante a errores de red."""
        headers = {"Referer": referer}
        for verify in [True, False]:
            try:
                r = session.head(url, headers=headers, timeout=10, verify=verify)
                return r.status_code == 200
            except requests.exceptions.ConnectionError:
                return False
            except requests.exceptions.Timeout:
                return False
            except Exception:
                continue
        return False

    def get_image_urls(self, session, cid: str):
        """Generador de URLs (compatibilidad con flujos alternativos)."""
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
            fails = 0 if found else fails + 1
            if fails >= 3:
                break