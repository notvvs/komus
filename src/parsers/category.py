import asyncio
from typing import List
from unicodedata import category

from bs4 import BeautifulSoup

from src.core.settings import settings
from src.parsers.base_parser import BaseParser
from src.scrapers.category import CategoryScraper


class CategoryParser(BaseParser):
    def __init__(self):
        self.scraper = CategoryScraper()

    async def parse_page(self, html: str):
        soup = BeautifulSoup(html, 'html.parser')
        links = []

        # Ищем все ссылки на товары
        product_links = soup.find_all('a', class_='product-plain__name js-product-variant-name')

        for link in product_links:
            href = link.get('href')
            if href:
                # Преобразуем в абсолютную ссылку
                if href.startswith('/'):
                    href = settings.base_url + href
                links.append(href)
        return links

    async def parse_all_category_pages(self, url: str) -> List:
        products_link = []

        category_links = await self.scraper.create_category_pages(url)
        for link in category_links:
            html = await self.scraper.scrape_page(link)
            page_products = await self.parse_page(html)
            products_link.extend(page_products)

        return products_link


parser = CategoryParser()

print(asyncio.run(parser.parse_all_category_pages("https://www.komus.ru/katalog/kantstovary/kalkulyatory/c/970/?from=menu-v1-vse_kategorii")))