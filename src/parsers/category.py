import asyncio
from typing import List
from bs4 import BeautifulSoup
from src.core.settings import settings
from src.parsers.base_parser import BaseParser
from src.scrapers.category import CategoryScraper


class CategoryParser(BaseParser):
    def __init__(self):
        self.scraper = CategoryScraper()

    async def parse_page(self, html: str):
        """Парсинг ссылок на товары со страницы"""
        soup = BeautifulSoup(html, 'html.parser')
        links = []

        # Ищем все ссылки на товары
        product_links = soup.find_all('a', class_='product-plain__name js-product-variant-name')

        for link in product_links:
            href = link.get('href')
            if href:
                # Преобразуем в абсолютную ссылку
                if href.startswith('/'):
                    href = settings.base_url.rstrip('/') + href
                links.append(href)
        return links

    async def parse_all_category_pages(self, page, url: str) -> List[str]:
        """Парсинг всех страниц категории"""
        products_link = []

        # Получаем ссылки на все страницы категории
        category_links = await self.scraper.create_category_pages(page, url)

        for link in category_links:
            # Получаем HTML страницы
            html = await self.scraper.scrape_page(page, link)
            # Парсим ссылки на товары
            page_products = await self.parse_page(html)
            products_link.extend(page_products)

        return products_link