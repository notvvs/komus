import asyncio
import math
from typing import List
from bs4 import BeautifulSoup
import logging

from src.core.settings import settings
from src.parsers.base_parser import BaseParser
from src.scrapers.scraper import PageScraper

logger = logging.getLogger(__name__)


class CategoryParser(BaseParser):
    def __init__(self):
        self.scraper = PageScraper()

    async def parse_page(self, category_url: str) -> List[str]:
        all_product_links = []

        try:
            category_pages = await self._get_category_pages(category_url)
            logger.info(f"Found {len(category_pages)} pages in category")

            for i, page_url in enumerate(category_pages, 1):
                logger.info(f"Processing page {i}/{len(category_pages)}")
                product_links = await self._get_product_links(page_url)
                all_product_links.extend(product_links)

                if i < len(category_pages):
                    await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error parsing category {category_url}: {e}")

        return all_product_links

    async def _get_category_pages(self, category_url: str) -> List[str]:
        try:
            html = await self.scraper.scrape_page(category_url)
            if not html:
                return [category_url]

            soup = BeautifulSoup(html, 'html.parser')
            total_pages = self._calculate_pages_count(soup)

            base_url = category_url.split('?')[0].rstrip('/')
            return [f"{base_url}/?sort=stockRelevance&page={page}"
                   for page in range(0, total_pages)]

        except Exception as e:
            logger.error(f"Error getting category pages: {e}")
            return [category_url]

    async def _get_product_links(self, page_url: str) -> List[str]:
        try:
            html = await self.scraper.scrape_page(page_url)
            if not html:
                return []

            soup = BeautifulSoup(html, 'html.parser')
            product_links = []

            links = soup.find_all('a', class_='product-plain__name js-product-variant-name')
            for link in links:
                href = link.get('href')
                if href:
                    if href.startswith('/'):
                        href = settings.base_url.rstrip('/') + href
                    product_links.append(href)

            logger.info(f"Found {len(product_links)} product links")
            return product_links

        except Exception as e:
            logger.error(f"Error getting product links: {e}")
            return []

    def _calculate_pages_count(self, soup: BeautifulSoup) -> int:
        try:
            items_count_elem = soup.find('span', class_="catalog__header-sup")
            if items_count_elem:
                items_count = int(items_count_elem.get_text(strip=True))
                return max(1, math.ceil(items_count / 30))
            return 1
        except (ValueError, AttributeError):
            return 1