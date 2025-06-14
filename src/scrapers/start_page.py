import asyncio
from src.scrapers.base_scraper import BaseScraper


class StartPageScraper(BaseScraper):

    async def scrape_page(self, page, url: str) -> str:
        """Получение HTML через Playwright"""
        await page.goto(url, wait_until='domcontentloaded', timeout=15000)
        await asyncio.sleep(2)  # Ждем полной загрузки
        return await page.content()