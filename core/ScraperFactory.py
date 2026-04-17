# /core/ScraperFactory.py
from scrapers.TMOHentaiScraper import TMOHentaiScraper

class ScraperFactory:
    _scrapers = [TMOHentaiScraper()] # Lista de sitios soportados

    @classmethod
    def get_scraper(cls, url: str):
        for s in cls._scrapers:
            if s.matches(url):
                return s
        return None