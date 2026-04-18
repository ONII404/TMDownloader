# /scrapers/LectorHentaiScraper.py
"""
Scraper para https://lectorhentai.com/

URLs soportadas:
    https://lectorhentai.com/manga/{id}/{slug}

Estrategia de imágenes:
    1. Visita la página del manga para obtener metadata y el total de páginas
       (los thumbnails del sprite tienen alt="Imagenes N/TOTAL").
    2. Visita la página del reader (/read/{id}/{slug}) para extraer las URLs
       reales de las imágenes desde el JS embebido o el DOM.
    3. Si el reader no devuelve URLs parseables, construye las URLs directamente
       desde el CDN usando el patrón del sprite (img5.giolandscaping.com/library/{id}/...).
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
        # fallback: solo el segmento final de la URL
        return url.rstrip("/").split("/")[-1]

    def get_image_tasks(self, session, cid: str, dest_dir) -> list:
        """
        Extrae las URLs de imágenes visitando la página del reader.
        Retorna lista de tuplas (url, dest_path, referer).
        """
        numeric_id, slug = self._split_cid(cid)
        manga_url  = f"{self._BASE}/manga/{numeric_id}/{slug}"
        reader_url = f"{self._BASE}/read/{numeric_id}/{slug}"

        tasks   = []
        referer = manga_url

        # 1 ── Intentar extraer imágenes del reader
        img_urls = self._fetch_reader_images(session, reader_url, manga_url)

        if not img_urls:
            # 2 ── Fallback: construir URLs desde el CDN usando el patrón del sprite
            img_urls = self._build_cdn_urls(session, manga_url, numeric_id)

        for i, url in enumerate(img_urls):
            ext      = self._guess_ext(url)
            dest     = Path(dest_dir) / f"{i:03d}{ext}"
            tasks.append((url, dest, referer))

        return tasks

    # ── Metadata ─────────────────────────────────────────────────────────────

    def get_metadata(self, session, cid: str) -> dict:
        meta = super().get_metadata(session, cid)
        numeric_id, slug = self._split_cid(cid)
        manga_url = f"{self._BASE}/manga/{numeric_id}/{slug}"
        meta["Web"] = manga_url

        try:
            resp = session.get(manga_url, timeout=15)
            if resp.status_code != 200:
                return meta
            html = resp.text
            meta.update(self._parse_metadata(html, manga_url))
        except Exception:
            pass

        return meta

    # ── Internos ─────────────────────────────────────────────────────────────

    def _split_cid(self, cid: str) -> tuple[str, str]:
        """
        Separa '{numeric_id}-{slug}' en (numeric_id, slug).
        Si no tiene guión (raro), trata todo como id y slug vacío.
        """
        parts = cid.split("-", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return cid, cid

    def _fetch_reader_images(self, session, reader_url: str, referer: str) -> list[str]:
        """
        Visita la página del reader y extrae las URLs de imágenes.

        El reader de lectorhentai usa ts_reader.run({...}) con este patrón:
            "images": ["//img5.giolandscaping.com/library/ID/000.webp", ...]

        Las URLs vienen sin protocolo (//...), se normalizan a https://.
        """
        def _fix_url(u: str) -> str:
            """Normaliza URLs protocol-relative a https://"""
            if u.startswith("//"):
                return "https:" + u
            return u

        try:
            headers = {"Referer": referer}
            resp = session.get(reader_url, headers=headers, timeout=15)
            if resp.status_code != 200:
                return []
            html = resp.text

            # ── Patrón 1 (principal): "images": [...] dentro de ts_reader.run()
            # Captura el array JSON que sigue a `"images":` o `"images" :`
            m = re.search(
                r'"images"\s*:\s*(\[[\s\S]*?\])',
                html
            )
            if m:
                try:
                    urls = json.loads(m.group(1))
                    if isinstance(urls, list) and urls:
                        result = [_fix_url(u) for u in urls
                                  if isinstance(u, str) and "giolandscaping.com" in u]
                        if result:
                            return result
                except Exception:
                    pass

            # ── Patrón 2: cualquier URL //img5.giolandscaping.com/library/ID/NNN.webp
            # Captura URLs protocol-relative o con https
            raw = re.findall(
                r'(?:https?:)?//img\d*\.giolandscaping\.com/library/\d+/\d{3}\.(?:webp|jpg|jpeg|png)',
                html
            )
            valid = [_fix_url(u) for u in raw
                     if "_sprite" not in u and "_cover" not in u]
            if valid:
                seen, deduped = set(), []
                for u in valid:
                    if u not in seen:
                        seen.add(u)
                        deduped.append(u)
                return deduped

            # ── Patrón 3: img[src] del readerarea (primera imagen cargada)
            # El HTML tiene <img ... src="//img5.giolandscaping.com/library/ID/000.webp">
            # y el total de páginas en los <option> del select
            m_img = re.search(
                r'<img[^>]+class="ts-main-image"[^>]+src="([^"]+)"',
                html
            )
            m_total = re.search(r'<option[^>]*>\d+/(\d+)</option>', html)
            if m_img and m_total:
                first_url = _fix_url(m_img.group(1))
                total     = int(m_total.group(1))
                # Construir el resto de URLs incrementando el número de página
                base_m = re.match(r'(https://[^/]+/library/\d+/)(\d{3})(\.(?:webp|jpg|jpeg|png))', first_url)
                if base_m:
                    base, _, ext = base_m.group(1), base_m.group(2), base_m.group(3)
                    return [f"{base}{i:03d}{ext}" for i in range(total)]

        except Exception:
            pass
        return []

    def _build_cdn_urls(self, session, manga_url: str, numeric_id: str) -> list[str]:
        """
        Fallback: si el reader no es accesible, obtiene el total de páginas
        del sprite (alt="Imagenes N/TOTAL") y construye las URLs directamente.
        El CDN usa el patrón:
            img5.giolandscaping.com/library/{numeric_id}/{hash}_{N}.webp
        donde el hash se extrae del sprite URL de la página del manga.
        """
        try:
            resp = session.get(manga_url, timeout=15)
            if resp.status_code != 200:
                return []
            html = resp.text

            # Extraer el hash del sprite URL
            # Ejemplo: //img5.giolandscaping.com/library/90168/69cb128e62dfe_sprite_0.webp
            m = re.search(
                r'//img5\.giolandscaping\.com/library/\d+/([a-f0-9]+)_sprite',
                html
            )
            if not m:
                return []
            file_hash = m.group(1)

            # Extraer total de páginas del último alt="Imagenes N/TOTAL"
            totals = re.findall(r'alt="Imagenes \d+/(\d+)"', html)
            if not totals:
                return []
            total = int(totals[-1])

            # Construir URLs — el CDN las nombra {hash}_{index}.webp (base 0)
            # Verificar el patrón real con la primera imagen
            base = f"https://img5.giolandscaping.com/library/{numeric_id}/{file_hash}"

            # Intentar con sufijo _{N} primero, luego sin sufijo
            test_url = f"{base}_0.webp"
            ok = self._head_ok(session, test_url, manga_url)
            if ok:
                return [f"{base}_{i}.webp" for i in range(total)]

            # Segundo patrón: directamente numerado (0.webp, 1.webp, ...)
            test_url2 = f"{base}_page_1.webp"
            ok2 = self._head_ok(session, test_url2, manga_url)
            if ok2:
                return [f"{base}_page_{i+1}.webp" for i in range(total)]

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
        """Extrae la extensión de la URL, con fallback a .webp."""
        m = re.search(r'\.(webp|jpg|jpeg|png|gif)(?:[?#]|$)', url, re.IGNORECASE)
        return f".{m.group(1).lower()}" if m else ".webp"

    def _parse_metadata(self, html: str, manga_url: str) -> dict:
        """Parsea los campos de metadata del HTML de la página del manga."""
        meta = {}

        # Título — limpiar sufijo " en Español | Leer Online Gratis"
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
                meta["Genre"] = genres[0].strip()   # primer género como genre principal

        # Tags
        m = re.search(
            r'<b>Tags:</b>.*?<span class="mgen">(.*?)</span>',
            html, re.DOTALL
        )
        if m:
            tags = re.findall(r'>([^<]+)</a>', m.group(1))
            if tags:
                # Combinar géneros + tags para el campo Tags del ComicInfo
                all_genres = re.findall(
                    r'<b>Generos:</b>.*?<span class="mgen">(.*?)</span>',
                    html, re.DOTALL
                )
                genre_list = []
                if all_genres:
                    genre_list = re.findall(r'>([^<]+)</a>', all_genres[0])
                combined = genre_list + tags
                meta["Tags"] = ", ".join(t.strip() for t in combined)

        # Idioma
        m = re.search(r'Idioma\s*<i>([^<]+)</i>', html)
        if m:
            lang = m.group(1).strip().lower()
            lang_map = {"español": "es", "ingles": "en", "inglés": "en",
                        "japanese": "ja", "japonés": "ja",
                        "portuguese": "pt", "portugués": "pt"}
            meta["LanguageISO"] = lang_map.get(lang, "es")

        # Año de publicación
        m = re.search(r'<time datetime="(\d{4})-\d{2}-\d{2}', html)
        if m:
            meta["Year"] = m.group(1)

        # Revista (Publisher)
        m = re.search(
            r'<b>Revistas</b>.*?<span class="mgen">(.*?)</span>',
            html, re.DOTALL
        )
        if m:
            revista_links = re.findall(r'>([^<]+)</a>', m.group(1))
            if revista_links:
                meta["Publisher"] = revista_links[0].strip()

        meta["Source"] = self._source_name
        meta["Web"]    = manga_url
        meta["Manga"]  = "Yes"

        return meta