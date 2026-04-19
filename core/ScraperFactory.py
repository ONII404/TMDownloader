# /core/ScraperFactory.py
from scrapers.TMOHentaiScraper    import TMOHentaiScraper
from scrapers.LectorHentaiScraper import LectorHentaiScraper
from scrapers.ONFMangasScraper    import ONFMangasScraper


class ScraperFactory:
    _scrapers = [
        TMOHentaiScraper(),
        LectorHentaiScraper(),
        ONFMangasScraper(),
    ]

    @classmethod
    def get_scraper(cls, url: str):
        for s in cls._scrapers:
            if s.matches(url):
                return s
        return None