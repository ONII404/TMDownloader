# /scrapers/BaseScraper.py
from abc import ABC, abstractmethod


class BaseScraper(ABC):

    # ── Obligatorios ────────────────────────────────────────────────────────

    @abstractmethod
    def matches(self, url: str) -> bool:
        """Retorna True si la URL pertenece a este sitio."""
        pass

    @abstractmethod
    def extract_id(self, url: str) -> str:
        """Extrae el identificador único del manga/capítulo."""
        pass

    @abstractmethod
    def get_image_tasks(self, session, cid: str, dest_dir) -> list:
        """
        Retorna lista de tuplas (url, dest_path, referer) para el DownloadEngine.
        """
        pass

    # ── Opcional (no abstracto) ──────────────────────────────────────────────

    def get_metadata(self, session, cid: str) -> dict:
        """
        Retorna un dict con campos de ComicInfo.xml.
        Los scrapers que puedan traer metadata real deben sobreescribir este método.

        Claves soportadas (todas opcionales):
            Title, Series, Number, Year, Writer, Publisher,
            Genre, Tags, LanguageISO, Source, Web, Summary,
            BlackAndWhite, Manga, PageCount

        Este método base retorna un dict mínimo genérico usando el cid y el
        nombre del scraper, de modo que siempre haya algo razonable en el CBZ.
        """
        source = getattr(self, "_source_name", self.__class__.__name__)
        return {
            "Title":       cid,
            "Series":      "Desconocido",
            "Writer":      "Desconocido",
            "Publisher":   "Desconocido",
            "Source":      source,
            "LanguageISO": "es",
            "Manga":       "Yes",
        }