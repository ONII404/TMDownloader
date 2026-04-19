# /scrapers/ONFMangasScraper.py
"""
Scraper para https://onfmangas.com/

URLs soportadas:
    Manga completo : https://onfmangas.com/manga/{id}/{slug}
    Capítulo único : https://onfmangas.com/lector/{chapter_id}/{slug}

Estrategia:
  - URL de manga  → extrae chaptersData (JSON embebido) y descarga todos
                    los capítulos en orden, cada uno como un .cbz separado
                    dentro de la misma carpeta de serie.
  - URL de lector → descarga solo ese capítulo.

Las imágenes están directamente en el DOM del lector como:
    <img class="manga-page" src="https://uploads.mangadex.org/data/{hash}/{N}-{longhash}.jpg"
         data-fallback="https://...">
No hay array JS; se parsean los src del HTML.
"""
import re
import json
from pathlib import Path

from scrapers.BaseScraper import BaseScraper


class ONFMangasScraper(BaseScraper):

    _source_name = "ONFMangas"
    _BASE        = "https://onfmangas.com"

    # ── Obligatorios ──────────────────────────────────────────────────────────

    def matches(self, url: str) -> bool:
        return "onfmangas.com" in url

    def extract_id(self, url: str) -> str:
        """
        Para URLs de manga  → retorna 'manga-{id}-{slug}'
        Para URLs de lector → retorna 'lector-{chapter_id}-{slug}'

        Este ID se usa como nombre de carpeta temporal y del .cbz.
        """
        m = re.search(r"/manga/(\d+)/([^/?#]+)", url)
        if m:
            return f"manga-{m.group(1)}-{m.group(2)}"

        m = re.search(r"/lector/(\d+)/([^/?#]+)", url)
        if m:
            return f"lector-{m.group(1)}-{m.group(2)}"

        return url.rstrip("/").split("/")[-1]

    def get_image_tasks(self, session, cid: str, dest_dir) -> list:
        """
        Para URLs de capítulo individual: extrae imágenes del lector.
        Para URLs de manga completo: este método NO se llama directamente;
        la descarga multi-capítulo la orquesta get_chapters().

        En el caso de capítulo individual (cid empieza con 'lector-'):
        visita la URL del lector y extrae los <img class="manga-page">.
        """
        if cid.startswith("lector-"):
            parts   = cid.split("-", 2)   # ['lector', chapter_id, slug]
            chapter_id = parts[1]
            slug       = parts[2] if len(parts) > 2 else ""
            reader_url = f"{self._BASE}/lector/{chapter_id}/{slug}"
            return self._tasks_from_reader(session, reader_url, dest_dir)

        # Para 'manga-...' el flujo multi-capítulo usa get_chapters() en su lugar
        return []

    # ── Multi-capítulo ────────────────────────────────────────────────────────

    def is_multi_chapter(self, url: str) -> bool:
        """Retorna True si la URL apunta a una página de manga (no a un lector)."""
        return bool(re.search(r"/manga/\d+/", url))

    def get_chapters(self, session, url: str) -> list[dict]:
        """
        Extrae la lista completa de capítulos de la página del manga.

        Retorna lista de dicts ordenada por número ASC:
            [
              {
                "id"      : "108153",
                "numero"  : "1.00",
                "titulo"  : "Capítulo 1",
                "url"     : "/lector/108153/capitulo-1",
              },
              ...
            ]
        """
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code != 200:
                return []
            html = resp.text

            # El sitio embebe el JSON completo en un <script>:
            # const chaptersData = [{...}, ...];
            m = re.search(
                r'const\s+chaptersData\s*=\s*(\[[\s\S]*?\]);',
                html
            )
            if not m:
                return []

            data = json.loads(m.group(1))
            # Ordenar por número ascendente
            data.sort(key=lambda c: float(c.get("numero", 0)))
            return data

        except Exception:
            return []

    def get_chapter_image_tasks(
        self,
        session,
        chapter: dict,
        dest_dir: Path,
        series_url: str,
    ) -> list:
        """
        Retorna las tareas de descarga para un capítulo específico.

        chapter   : dict de get_chapters()
        dest_dir  : carpeta temporal donde se guardarán las imágenes
        series_url: URL de la página del manga (para el Referer)
        """
        reader_url = self._BASE + chapter["url"]
        return self._tasks_from_reader(session, reader_url, dest_dir, referer=series_url)

    # ── Metadata ──────────────────────────────────────────────────────────────

    def get_metadata(self, session, cid: str) -> dict:
        meta = super().get_metadata(session, cid)

        if cid.startswith("manga-"):
            parts    = cid.split("-", 2)
            manga_id = parts[1]
            slug     = parts[2] if len(parts) > 2 else ""
            page_url = f"{self._BASE}/manga/{manga_id}/{slug}"
        elif cid.startswith("lector-"):
            # Para capítulo individual no tenemos la URL del manga directamente;
            # retornamos metadata mínima
            return meta
        else:
            return meta

        try:
            resp = session.get(page_url, timeout=15)
            if resp.status_code == 200:
                meta.update(self._parse_manga_metadata(resp.text, page_url))
        except Exception:
            pass

        return meta

    def get_series_metadata(self, session, manga_url: str) -> dict:
        """
        Metadata completa de la serie para ser usada en todos sus capítulos.
        Retorna un dict listo para pasar a ComicInfo con Series, Title, Genre, etc.
        """
        meta = super().get_metadata(session, "")
        try:
            resp = session.get(manga_url, timeout=15)
            if resp.status_code == 200:
                meta.update(self._parse_manga_metadata(resp.text, manga_url))
        except Exception:
            pass
        return meta

    def build_chapter_metadata(self, series_meta: dict, chapter: dict) -> dict:
        """
        Combina la metadata de la serie con la info del capítulo individual.
        El 'Title' será el nombre del capítulo; 'Series' queda como serie.
        """
        meta = dict(series_meta)
        numero = chapter.get("numero", "")
        titulo = chapter.get("titulo", "")

        # Number: usar el número limpio (ej: "1" en vez de "1.00")
        try:
            num_float = float(numero)
            meta["Number"] = str(int(num_float)) if num_float == int(num_float) else str(num_float)
        except (ValueError, TypeError):
            meta["Number"] = numero

        # Title del capítulo para el .cbz
        meta["Title"] = titulo or f"Capítulo {meta['Number']}"

        return meta

    # ── Internos ──────────────────────────────────────────────────────────────

    def _tasks_from_reader(
        self,
        session,
        reader_url: str,
        dest_dir,
        referer: str = "",
    ) -> list:
        """
        Visita la página del lector y extrae todas las imágenes
        <img class="manga-page" src="..." data-fallback="...">.

        Usa data-fallback como segundo intento si el src falla.
        Retorna lista de tuplas (url, dest_path, referer).
        """
        referer = referer or reader_url
        try:
            resp = session.get(
                reader_url,
                headers={"Referer": referer},
                timeout=15,
            )
            if resp.status_code != 200:
                return []
            html = resp.text

            # Extraer todos los <img class="manga-page" src="...">
            # Patrón: src puede estar en un CDN de mangadex u otro
            img_tags = re.findall(
                r'<img[^>]+class="manga-page[^"]*"[^>]+>',
                html,
                re.IGNORECASE,
            )

            tasks = []
            for i, tag in enumerate(img_tags):
                # src principal
                src_m = re.search(r'\bsrc="([^"]+)"', tag)
                if not src_m:
                    continue
                src = src_m.group(1)

                # Ignorar placeholders / SVG de carga
                if not src or src.endswith(".svg") or "readerarea.svg" in src:
                    continue

                ext  = self._guess_ext(src)
                dest = Path(dest_dir) / f"{i:03d}{ext}"
                tasks.append((src, dest, referer))

            return tasks

        except Exception:
            return []

    def _parse_manga_metadata(self, html: str, page_url: str) -> dict:
        """Extrae metadata de la página del manga."""
        meta = {}

        # Título
        m = re.search(r'<h1[^>]+class="manga-title"[^>]*>([\s\S]*?)</h1>', html)
        if m:
            title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            meta["Title"]  = title
            meta["Series"] = title

        # Año
        m = re.search(r'<span>Manga</span>\s*•\s*<span>(\d{4})</span>', html)
        if m:
            meta["Year"] = m.group(1)

        # Géneros
        genres = re.findall(
            r'<a[^>]+class="genre-tag"[^>]*>([^<]+)</a>',
            html
        )
        if genres:
            meta["Genre"] = genres[0].strip()
            meta["Tags"]  = ", ".join(g.strip() for g in genres)

        # Descripción
        m = re.search(r'<div[^>]+class="manga-description"[^>]*>([\s\S]*?)</div>', html)
        if m:
            desc = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            desc = re.sub(r'\s+', ' ', desc)
            if desc:
                meta["Summary"] = desc[:500]   # limitar longitud

        meta["Source"]      = self._source_name
        meta["Web"]         = page_url
        meta["Manga"]       = "Yes"
        meta["LanguageISO"] = "es"

        return meta

    def _guess_ext(self, url: str) -> str:
        m = re.search(r'\.(webp|jpg|jpeg|png|gif)(?:[?#]|$)', url, re.IGNORECASE)
        return f".{m.group(1).lower()}" if m else ".jpg"
