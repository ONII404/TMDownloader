# /scrapers/TMOHentaiScraper.py
"""
Scraper para https://tmohentai.com/

Soporta:
  - Descarga individual de capítulos / oneshots
  - Metadata desde la página web (og:title, tags, autor...)
  - Metadata enriquecida desde TMOH.json (si existe en la raíz del proyecto)

Emparejamiento TMOH.json:
  URL descargada : https://tmohentai.com/contents/69b6fd0b4a6fa
  Campo en JSON  : "url": "/contents/69b6fd0b4a6fa"
  Clave de match : "69b6fd0b4a6fa"  (parte final de la URL en ambos lados)
"""
import re
import json
import requests
from pathlib import Path
from scrapers.BaseScraper import BaseScraper
from scrapers.sites import TMO_BASE, TMO_CDN_HOSTS, TMO_SOURCE_NAME

# Ruta del JSON de metadata externa (raíz del proyecto)
_TMOH_JSON = Path(__file__).parent.parent / "TMOH.json"


class TMOHentaiScraper(BaseScraper):

    _source_name = TMO_SOURCE_NAME
    _BASE        = TMO_BASE

    def __init__(self):
        self.cdn_hosts = list(TMO_CDN_HOSTS)
        self.extensions = [".webp", ".jpg", ".jpeg", ".png"]

        # Índice de metadata del JSON externo: { content_id: meta_dict }
        self._json_index: dict[str, dict] = {}
        self._json_load_error: str | None = None  # error diferido
        self._json_announced: bool = False         # evitar repetir el aviso
        self._load_tmoh_json()

    # ── Carga de TMOH.json ────────────────────────────────────────────────────

    def _load_tmoh_json(self):
        """
        Carga y construye el índice de TMOH.json.

        Estructura esperada del JSON (array de objetos):
        [
          {
            "url":         "/contents/69b6fd0b4a6fa",
            "title":       "Título del manga",
            "artist":      "Artista",
            "author":      "Autor",
            "description": "Descripción...",
            "genre":       "Hentai",
            "chapters":    [{"chapterNumber": "1"}, ...]
          },
          ...
        ]

        El campo "url" puede ser:
          - "/contents/69b6fd0b4a6fa"
          - "https://tmohentai.com/contents/69b6fd0b4a6fa"
          - "69b6fd0b4a6fa"   (solo el ID)
        """
        if not _TMOH_JSON.exists():
            return

        try:
            data = json.loads(_TMOH_JSON.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                return

            for entry in data:
                raw_url = entry.get("url", "")
                # Extraer solo el ID (parte final)
                cid = self._id_from_url(raw_url) or raw_url.strip("/")
                if cid:
                    self._json_index[cid] = entry

            # No imprimimos aquí: el scraper se instancia al importar
            # ScraperFactory, antes de que argparse procese --version/--help.
            # El aviso se emite en get_metadata() al hacer la primera descarga.
            pass
        except Exception as e:
            self._json_load_error = str(e)

    @staticmethod
    def _id_from_url(url: str) -> str:
        """Extrae el ID de contenido del final de la URL de tmohentai."""
        m = re.search(r"/(?:contents|reader)/([a-zA-Z0-9]+)", url)
        return m.group(1) if m else ""

    # ── Obligatorios ────────────────────────────────────────────────────────

    def matches(self, url: str) -> bool:
        domain = TMO_BASE.split("//")[1]  # "tmohentai.com"
        return domain in url or (len(url) == 13 and url.isalnum())

    def extract_id(self, url: str) -> str:
        cid = self._id_from_url(url)
        return cid if cid else url

    def get_image_tasks(self, session, cid: str, dest_dir) -> list:
        """
        Probing HEAD para descubrir imágenes en el CDN.
        Para cada índice rota el host de inicio pero prueba TODOS los hosts,
        igual que hace el navegador (y el script original).
        Retorna lista de (url, dest_path, referer).
        """
        tasks   = []
        referer = f"{self._BASE}/reader/{cid}/cascade"
        fails   = 0
        n_hosts = len(self.cdn_hosts)

        print(f"  Patrón CDN: https://{self.cdn_hosts[0]}/contents/{cid}/000.webp")

        for i in range(1000):
            found = False
            # Rotar el host de inicio según el índice, luego probar todos en orden
            host_order = (
                self.cdn_hosts[i % n_hosts:] + self.cdn_hosts[:i % n_hosts]
            )

            for ext in self.extensions:
                if found:
                    break
                for host in host_order:
                    img_url = f"https://{host}/contents/{cid}/{i:03d}{ext}"
                    if self._head_ok(session, img_url, referer):
                        dest_file = Path(dest_dir) / f"{i:03d}{ext}"
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
        Combina metadata de dos fuentes con prioridad:
          1. TMOH.json (si existe entrada para el cid)
          2. Scraping de la página web
          3. Fallbacks genéricos del BaseScraper
        """
        meta = super().get_metadata(session, cid)
        meta["Web"] = f"{self._BASE}/contents/{cid}"

        # Emitir aviso de TMOH.json una sola vez, en el contexto de una descarga real
        if not self._json_announced:
            self._json_announced = True
            if self._json_load_error:
                print(f"  [!] Error al leer TMOH.json: {self._json_load_error}")
            elif self._json_index:
                print(f"  [i] TMOH.json: {len(self._json_index)} entradas cargadas.")

        # ── Fuente 1: TMOH.json ────────────────────────────────────────────
        json_meta = self._meta_from_json(cid)

        # ── Fuente 2: Scraping web ─────────────────────────────────────────
        web_meta = {}
        try:
            url  = f"{self._BASE}/contents/{cid}"
            resp = session.get(url, timeout=15)
            if resp.status_code == 200:
                web_meta = self._parse_web_metadata(resp.text, cid)
        except Exception:
            pass

        # Merge: web_meta base, json_meta tiene prioridad si tiene el campo
        meta.update(web_meta)
        meta.update(json_meta)   # JSON sobreescribe lo scrapeado

        return meta

    def _meta_from_json(self, cid: str) -> dict:
        """
        Construye un dict de ComicInfo desde la entrada TMOH.json del cid.
        Retorna dict vacío si no hay entrada.
        """
        entry = self._json_index.get(cid)
        if not entry:
            return {}

        meta = {}

        title = entry.get("title", "").strip()
        if title:
            meta["Title"]  = title
            meta["Series"] = title

        artist = entry.get("artist", "").strip()
        author = entry.get("author", "").strip()
        writer = ", ".join(filter(None, [author, artist]))
        if writer:
            meta["Writer"] = writer

        description = entry.get("description", "").strip()
        if description:
            meta["Summary"] = description[:500]

        genre = entry.get("genre", "")
        if isinstance(genre, list):
            genre = ", ".join(g.strip() for g in genre if g.strip())
        elif isinstance(genre, str):
            genre = genre.strip()
        if genre:
            meta["Genre"] = genre
            meta["Tags"]  = genre

        # Número de capítulo desde el primer elemento de "chapters"
        chapters = entry.get("chapters", [])
        if chapters and isinstance(chapters, list):
            first = chapters[0]
            num   = first.get("chapterNumber", "") if isinstance(first, dict) else ""
            if num:
                meta["Number"] = str(num)

        return meta

    def _parse_web_metadata(self, html: str, cid: str) -> dict:
        """Extrae metadata scrapeando el HTML de la página del contenido."""
        meta = {}

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
            meta["Genre"] = tags[0].strip()

        # Idioma
        if re.search(r'español|spanish', html, re.IGNORECASE):
            meta["LanguageISO"] = "es"
        elif re.search(r'english', html, re.IGNORECASE):
            meta["LanguageISO"] = "en"
        elif re.search(r'japanese', html, re.IGNORECASE):
            meta["LanguageISO"] = "ja"

        meta["Source"] = self._source_name
        meta["Web"]    = f"{self._BASE}/contents/{cid}"

        return meta

    # ── Interno ─────────────────────────────────────────────────────────────

    def _head_ok(self, session, url: str, referer: str) -> bool:
        """HEAD request tolerante a errores de red. Señala bloqueos CF."""
        headers = {"Referer": referer}
        for verify in [True, False]:
            try:
                r = session.head(url, headers=headers, timeout=10, verify=verify)
                if r.status_code in {403, 429, 503}:
                    # Importar aquí para evitar ciclo de imports
                    try:
                        from utils.BatchManager import signal_cloudflare
                        signal_cloudflare()
                    except ImportError:
                        pass
                    return False
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
        referer = f"{self._BASE}/reader/{cid}/cascade"
        fails   = 0
        n_hosts = len(self.cdn_hosts)
        for i in range(1000):
            found = False
            host_order = (
                self.cdn_hosts[i % n_hosts:] + self.cdn_hosts[:i % n_hosts]
            )
            for ext in self.extensions:
                if found:
                    break
                for host in host_order:
                    img_url = f"https://{host}/contents/{cid}/{i:03d}{ext}"
                    if self._head_ok(session, img_url, referer):
                        yield img_url
                        found = True
                        break
            fails = 0 if found else fails + 1
            if fails >= 3:
                break