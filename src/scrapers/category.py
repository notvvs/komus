import asyncio
import math
from typing import List
from bs4 import BeautifulSoup
from src.scrapers.base_scraper import BaseScraper


class CategoryScraper(BaseScraper):

    async def scrape_page(self, page, url: str) -> str:
        """Получение HTML через Playwright"""
        await page.goto(url, wait_until='domcontentloaded', timeout=15000)
        await asyncio.sleep(2)
        return await page.content()

    async def create_category_pages(self, page, url: str) -> List[str]:
        """Создание ссылок на все страницы категории"""
        category_pages = []

        # Переходим на страницу категории
        await page.goto(url, wait_until='domcontentloaded', timeout=15000)
        await asyncio.sleep(2)

        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')

        # Получаем количество страниц
        page_cnt = await self._get_pages_count(soup)

        base_url = url.split('?')[0].rstrip('/')

        # Создаем ссылки на все страницы с фильтром "в наличии"
        for page_number in range(page_cnt):
            filtered_url = f"{base_url}/f/stocklevelstatus=instock/?page={page_number}"
            category_pages.append(filtered_url)

        return category_pages

    async def _get_pages_count(self, soup: BeautifulSoup) -> int:
        """Получение количества страниц в категории"""
        try:
            items_cnt_elem = soup.find('span', class_="catalog__header-sup")
            if items_cnt_elem:
                items_cnt = items_cnt_elem.get_text(strip=True)
                pages_cnt = math.ceil(int(items_cnt) / 30)
                return pages_cnt
            return 1
        except:
            return 1