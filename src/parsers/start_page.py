import asyncio
from typing import List, Callable
from bs4 import BeautifulSoup
import logging

from src.core.settings import settings
from src.parsers.base_parser import BaseParser
from src.scrapers.scraper import PageScraper

logger = logging.getLogger(__name__)


class StartPageParser(BaseParser):
    def __init__(self):
        self.scraper = PageScraper()
        self.visited = set()
        self.processed_count = 0

    async def parse_page(self, *args, **kwargs) -> List[str]:
        return []

    async def parse_and_process(self, process_category_func: Callable) -> int:
        self.process_category = process_category_func

        categories_url = 'https://www.komus.ru/katalog/c/0/?from=menu-v1-vse_kategorii'

        html = await self.scraper.scrape_page(categories_url)
        if not html:
            return 0

        main_categories = self._extract_categories(html)
        logger.info(f"Found main categories: {len(main_categories)}")

        for i, category_url in enumerate(main_categories):
            logger.info(f"Main category {i + 1}/{len(main_categories)}")
            await self._process_category_recursive(category_url)

        return self.processed_count

    async def _process_category_recursive(self, category_url: str, level: int = 0):
        if category_url in self.visited:
            return

        self.visited.add(category_url)
        indent = "  " * level

        try:
            logger.info(f"{indent}Checking: {category_url}")

            html = await self.scraper.scrape_page(category_url)
            if not html:
                return

            soup = BeautifulSoup(html, 'html.parser')

            if self._has_products(soup):
                logger.info(f"{indent}Found category with products")
                self.processed_count += 1
                await self.process_category(category_url, self.processed_count)
                return

            subcategories = self._extract_categories(html)

            if subcategories:
                logger.info(f"{indent}Found subcategories: {len(subcategories)}")
                for subcat_url in subcategories:
                    if subcat_url not in self.visited:
                        await self._process_category_recursive(subcat_url, level + 1)

        except Exception as e:
            logger.error(f"{indent}Error processing {category_url}: {e}")

    def _has_products(self, soup: BeautifulSoup) -> bool:
        return bool(soup.find('div', class_='product-plain') or
                    soup.find('a', class_='product-plain__name'))

    def _extract_categories(self, html: str) -> List[str]:
        if isinstance(html, str):
            soup = BeautifulSoup(html, 'html.parser')
        else:
            soup = html

        categories = []
        category_links = soup.find_all('a', class_='categories__name')

        for link in category_links:
            href = link.get('href', '')
            if href and '/katalog/' in href:
                full_url = settings.base_url.rstrip('/') + href if href.startswith('/') else href
                categories.append(full_url)

        return categories