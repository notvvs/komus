from typing import List

from bs4 import BeautifulSoup

from src.scrapers.base_scraper import BaseScraper
from src.utils.http import fetch
from src.utils.pages_count import pages_count
from src.utils.session import create_komus_session


class CategoryScraper(BaseScraper):

    async def scrape_page(self, url: str) -> str:
        async with create_komus_session() as session:
            html = await fetch(session, url)
            return html

    async def create_category_pages(self, url: str) -> List:
        category_pages = []

        async with create_komus_session() as session:
            html = await fetch(session, url)

            soup = BeautifulSoup(html, 'html.parser')
            page_cnt = await pages_count(soup)

            base_url = url.split('?')[0]

            # Убираем слэш в конце, если есть
            base_url = base_url.rstrip('/')

            for page_number in range(page_cnt - 1):
                filtered_url = f"{base_url}/f/stocklevelstatus=instock/?page={page_number}"
                category_pages.append(filtered_url)

        return category_pages

