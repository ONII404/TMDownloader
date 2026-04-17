# /scrapers/BaseScraper.py
from abc import ABC, abstractmethod

class BaseScraper(ABC):
    @abstractmethod
    def matches(self, url: str) -> bool:
        """Retorna True si la URL pertenece a este sitio."""
        pass

    @abstractmethod
    def extract_id(self, url: str) -> str:
        """Extrae el identificador único del manga."""
        pass

    @abstractmethod
    def get_image_tasks(self, session, cid: str, dest_dir) -> list:
        """
        Retorna una lista de tuplas (url, dest_path, referer)
        que el DownloadEngine usará para descargar en paralelo.
        """
        pass