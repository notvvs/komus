from src.scrapers.base_scraper import BaseScraper
from src.utils.http import fetch
from src.utils.session import create_komus_session


class StartPageScraper(BaseScraper):

    async def scrape_page(self, url: str) -> str:
        async with create_komus_session() as session:
            html = await fetch(session, url)
            return html


