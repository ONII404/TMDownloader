# /core/ScraperFactory.py
from scrapers.TMOHentaiScraper import TMOHentaiScraper
from scrapers.LectorHentaiScraper import LectorHentaiScraper

class ScraperFactory:
    _scrapers = [
        TMOHentaiScraper(),
        LectorHentaiScraper(),
    ]

    @classmethod
    def get_scraper(cls, url: str):
        for s in cls._scrapers:
            if s.matches(url):
                return s
        return None