import asyncio
from typing import List
from bs4 import BeautifulSoup

from src.core.settings import settings
from src.parsers.base_parser import BaseParser


class StartPageParser(BaseParser):
    """Интегрированный парсер главной страницы - объединяет scraping и parsing"""

    async def parse_page(self, page) -> List[str]:
        """Главный метод - получает все категории с главной страницы"""
        categories_url = 'https://www.komus.ru/katalog/c/0/?from=menu-v1-vse_kategorii'

        html = await self._get_page_html(page, categories_url)
        categories = self._extract_category_links(html)

        return categories

    async def _get_page_html(self, page, url: str) -> str:
        """Получение HTML страницы через Playwright"""
        await page.goto(url, wait_until='domcontentloaded', timeout=settings.page_timeout)
        await asyncio.sleep(settings.page_load_delay)
        return await page.content()

    def _extract_category_links(self, html: str) -> List[str]:
        """Извлечение ссылок на категории из HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        category_links = []

        category_blocks = soup.find_all('div', class_="categories__item")

        for category_block in category_blocks:
            subcategories = category_block.find_all('li', class_="categories__subcategory")

            for subcategory in subcategories:
                link_elem = subcategory.find('a', class_="categories__link")

                if link_elem and link_elem.get('href'):
                    href = link_elem['href']

                    if href.startswith('/'):
                        full_url = settings.base_url.rstrip('/') + href
                    else:
                        full_url = href

                    category_links.append(full_url)

        return category_links