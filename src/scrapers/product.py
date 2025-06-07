from src.scrapers.base_scraper import BaseScraper
from src.utils.http import fetch
from src.utils.session import create_komus_session


class ProductScraper(BaseScraper):

    def add_specifications_tab(self, url: str) -> str:
        if '?' in url:
            return url + '&tabId=specifications'
        else:
            return url + '?tabId=specifications'

    async def scrape_page(self, url: str) -> str:
        async with create_komus_session() as session:
            html = await fetch(session, self.add_specifications_tab(url))
            return html