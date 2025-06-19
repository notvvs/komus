import asyncio
import math
from typing import List
from bs4 import BeautifulSoup

from src.core.settings import settings
from src.parsers.base_parser import BaseParser


class CategoryParser(BaseParser):
    """Интегрированный парсер категорий - объединяет scraping и parsing"""

    async def parse_page(self, page, category_url: str) -> List[str]:
        """Главный метод - возвращает все ссылки на товары из категории"""
        all_product_links = []

        category_page_urls = await self._get_category_pages(page, category_url)

        for page_url in category_page_urls:
            product_links = await self._get_product_links_from_page(page, page_url)
            all_product_links.extend(product_links)

        return all_product_links

    async def _get_category_pages(self, page, category_url: str) -> List[str]:
        """Получение ссылок на все страницы категории"""
        await page.goto(category_url, wait_until='domcontentloaded', timeout=settings.page_timeout)
        await asyncio.sleep(settings.page_load_delay)

        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')
        total_pages = self._calculate_pages_count(soup)

        base_url = category_url.split('?')[0].rstrip('/')
        category_pages = []

        for page_number in range(total_pages):
            page_url = f"{base_url}/f/stocklevelstatus=instock/?page={page_number}"
            category_pages.append(page_url)

        return category_pages

    async def _get_product_links_from_page(self, page, page_url: str) -> List[str]:
        """Получение ссылок на товары с одной страницы"""
        await page.goto(page_url, wait_until='domcontentloaded', timeout=settings.page_timeout)
        await asyncio.sleep(settings.page_load_delay)

        html = await page.content()
        return self._parse_product_links_from_html(html)

    def _parse_product_links_from_html(self, html: str) -> List[str]:
        """Парсинг ссылок на товары из HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        product_links = []

        links = soup.find_all('a', class_='product-plain__name js-product-variant-name')

        for link in links:
            href = link.get('href')
            if href:
                if href.startswith('/'):
                    href = settings.base_url.rstrip('/') + href
                product_links.append(href)

        return product_links

    def _calculate_pages_count(self, soup: BeautifulSoup) -> int:
        """Вычисление количества страниц в категории"""
        try:
            items_count_elem = soup.find('span', class_="catalog__header-sup")

            if items_count_elem:
                items_count_text = items_count_elem.get_text(strip=True)
                items_count = int(items_count_text)

                pages_count = math.ceil(items_count / 30)
                return max(1, pages_count)

            return 1

        except (ValueError, AttributeError):
            return 1