# /scrapers/LectorHentaiScraper.py
"""
Scraper para https://lectorhentai.com/

URLs soportadas:
    https://lectorhentai.com/manga/{id}/{slug}

Estrategia de imágenes:
    1. Visita la página del reader (/read/{id}/{slug}) y extrae el array
       "images" del bloque ts_reader.run({...}).
    2. Fallback: construye URLs desde el sprite de la página del manga
       (solo funciona con el patrón numérico antiguo).
"""
import re
import json
import requests
from pathlib import Path
from scrapers.BaseScraper import BaseScraper


class LectorHentaiScraper(BaseScraper):

    _source_name = "LectorHentai"
    _BASE        = "https://lectorhentai.com"

    # ── Obligatorios ─────────────────────────────────────────────────────────

    def matches(self, url: str) -> bool:
        return "lectorhentai.com" in url

    def extract_id(self, url: str) -> str:
        """
        Retorna '{numeric_id}-{slug}' para usarlo como nombre de carpeta/archivo.
        Ejemplo: '90168-akari-chan-se-mi-onahole-parte-1'
        """
        m = re.search(r"/manga/(\d+)/([^/?#]+)", url)
        if m:
            return f"{m.group(1)}-{m.group(2)}"
        return url.rstrip("/").split("/")[-1]

    def get_image_tasks(self, session, cid: str, dest_dir) -> list:
        """
        Extrae las URLs de imágenes visitando la página del reader.
        Retorna lista de tuplas (url, dest_path, referer).
        """
        numeric_id, slug = self._split_cid(cid)
        manga_url  = f"{self._BASE}/manga/{numeric_id}/{slug}"
        reader_url = f"{self._BASE}/read/{numeric_id}/{slug}"

        img_urls = self._fetch_reader_images(session, reader_url, manga_url)

        if not img_urls:
            img_urls = self._build_cdn_urls(session, manga_url, numeric_id)

        tasks = []
        for i, url in enumerate(img_urls):
            ext  = self._guess_ext(url)
            dest = Path(dest_dir) / f"{i:03d}{ext}"
            tasks.append((url, dest, manga_url))

        return tasks

    # ── Metadata ─────────────────────────────────────────────────────────────

    def get_metadata(self, session, cid: str) -> dict:
        meta = super().get_metadata(session, cid)
        numeric_id, slug = self._split_cid(cid)
        manga_url = f"{self._BASE}/manga/{numeric_id}/{slug}"
        meta["Web"] = manga_url

        try:
            resp = session.get(manga_url, timeout=15)
            if resp.status_code == 200:
                meta.update(self._parse_metadata(resp.text, manga_url))
        except Exception:
            pass

        return meta

    # ── Internos ─────────────────────────────────────────────────────────────

    def _split_cid(self, cid: str) -> tuple[str, str]:
        parts = cid.split("-", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return cid, cid

    def _fetch_reader_images(self, session, reader_url: str, referer: str) -> list[str]:
        """
        Visita la página del reader y extrae las URLs de imágenes desde
        el bloque ts_reader.run({...}).

        Las imágenes pueden tener nombres numéricos (000.webp) O hashes
        aleatorios (6zjtO1.jpg) — ambos casos son soportados.
        Las URLs vienen sin protocolo (//...), se normalizan a https://.
        """
        def _fix(u: str) -> str:
            return "https:" + u if u.startswith("//") else u

        try:
            resp = session.get(reader_url, headers={"Referer": referer}, timeout=15)
            if resp.status_code != 200:
                return []
            html = resp.text

            # ── Patrón principal: array "images" dentro de ts_reader.run()
            # Captura el JSON array completo que sigue a `"images":`
            m = re.search(r'"images"\s*:\s*(\[[\s\S]*?\])', html)
            if m:
                try:
                    urls = json.loads(m.group(1))
                    if isinstance(urls, list) and urls:
                        # Aceptar cualquier URL de giolandscaping.com,
                        # sin importar si el filename es numérico o hash
                        result = [
                            _fix(u) for u in urls
                            if isinstance(u, str) and "giolandscaping.com" in u
                        ]
                        if result:
                            return result
                except Exception:
                    pass

            # ── Fallback: cualquier URL de giolandscaping en el HTML
            # (cubre casos donde ts_reader.run usa una estructura distinta)
            raw = re.findall(
                r'(?:https?:)?//img\d*\.giolandscaping\.com/library/\d+/[^"\s]+',
                html
            )
            valid = [_fix(u) for u in raw if "_sprite" not in u and "_cover" not in u]
            if valid:
                seen, deduped = set(), []
                for u in valid:
                    if u not in seen:
                        seen.add(u)
                        deduped.append(u)
                return deduped

        except Exception:
            pass

        return []

    def _build_cdn_urls(self, session, manga_url: str, numeric_id: str) -> list[str]:
        """
        Fallback legacy: construye URLs desde el sprite con patrón numérico.
        Solo funciona en mangas con el formato antiguo de CDN (000.webp).
        """
        try:
            resp = session.get(manga_url, timeout=15)
            if resp.status_code != 200:
                return []
            html = resp.text

            m = re.search(
                r'//img5\.giolandscaping\.com/library/\d+/([a-f0-9]+)_sprite',
                html
            )
            if not m:
                return []
            file_hash = m.group(1)

            totals = re.findall(r'alt="Imagenes \d+/(\d+)"', html)
            if not totals:
                return []
            total = int(totals[-1])

            base     = f"https://img5.giolandscaping.com/library/{numeric_id}/{file_hash}"
            test_url = f"{base}_0.webp"
            if self._head_ok(session, test_url, manga_url):
                return [f"{base}_{i}.webp" for i in range(total)]

        except Exception:
            pass

        return []

    def _head_ok(self, session, url: str, referer: str) -> bool:
        try:
            r = session.head(url, headers={"Referer": referer}, timeout=10)
            return r.status_code == 200
        except Exception:
            return False

    def _guess_ext(self, url: str) -> str:
        """Extrae la extensión de la URL, con fallback a .jpg."""
        m = re.search(r'\.(webp|jpg|jpeg|png|gif)(?:[?#]|$)', url, re.IGNORECASE)
        return f".{m.group(1).lower()}" if m else ".jpg"

    def _parse_metadata(self, html: str, manga_url: str) -> dict:
        """Parsea los campos de metadata del HTML de la página del manga."""
        meta = {}

        # Título
        m = re.search(r'<h1[^>]+class="entry-title"[^>]*>([^<]+)</h1>', html)
        if m:
            title = re.sub(r'\s+en Español.*$', '', m.group(1).strip())
            title = re.sub(r'\s*\|\s*Leer.*$', '', title).strip()
            meta["Title"]  = title
            meta["Series"] = title

        # Artista/Writer
        m = re.search(
            r'<b>Artista</b>.*?<span class="mgen">(.*?)</span>',
            html, re.DOTALL
        )
        if m:
            artists = re.findall(r'>([^<]+)</a>', m.group(1))
            if artists:
                meta["Writer"] = ", ".join(a.strip() for a in artists)

        # Géneros
        m = re.search(
            r'<b>Generos:</b>.*?<span class="mgen">(.*?)</span>',
            html, re.DOTALL
        )
        if m:
            genres = re.findall(r'>([^<]+)</a>', m.group(1))
            if genres:
                meta["Genre"] = genres[0].strip()

        # Tags (géneros + tags combinados)
        genre_list = []
        mg = re.search(
            r'<b>Generos:</b>.*?<span class="mgen">(.*?)</span>',
            html, re.DOTALL
        )
        if mg:
            genre_list = re.findall(r'>([^<]+)</a>', mg.group(1))

        mt = re.search(
            r'<b>Tags:</b>.*?<span class="mgen">(.*?)</span>',
            html, re.DOTALL
        )
        if mt:
            tags = re.findall(r'>([^<]+)</a>', mt.group(1))
            combined = genre_list + tags
            if combined:
                meta["Tags"] = ", ".join(t.strip() for t in combined)

        # Idioma
        m = re.search(r'Idioma\s*<i>([^<]+)</i>', html)
        if m:
            lang_map = {
                "español": "es", "ingles": "en", "inglés": "en",
                "japanese": "ja", "japonés": "ja",
                "portuguese": "pt", "portugués": "pt",
            }
            meta["LanguageISO"] = lang_map.get(m.group(1).strip().lower(), "es")

        # Año
        m = re.search(r'<time datetime="(\d{4})-\d{2}-\d{2}', html)
        if m:
            meta["Year"] = m.group(1)

        # Revista (Publisher)
        m = re.search(
            r'<b>Revistas</b>.*?<span class="mgen">(.*?)</span>',
            html, re.DOTALL
        )
        if m:
            revistas = re.findall(r'>([^<]+)</a>', m.group(1))
            if revistas:
                meta["Publisher"] = revistas[0].strip()

        meta["Source"] = self._source_name
        meta["Web"]    = manga_url
        meta["Manga"]  = "Yes"

        return meta