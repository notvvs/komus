import asyncio
import logging
from typing import List

from src.parsers.start_page import StartPageParser
from src.parsers.category import parser as category_parser
from src.parsers.product_feature import KomusParser
from src.repository.mongo_client import mongo_client
from src.repository.repository import ProductRepository
from src.scrapers.start_page import StartPageScraper
from src.scrapers.product import ProductScraper
from src.utils.create_driver import get_page


logger = logging.getLogger(__name__)


class KomusParserService:
    def __init__(self):
        self.start_page_scraper = StartPageScraper()
        self.start_page_parser = StartPageParser()
        self.product_scraper = ProductScraper()


    async def __aenter__(self):
        await mongo_client.connect()
        self.product_repository = ProductRepository()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await mongo_client.disconnect()

    async def run_parsing(self, limit_categories: int = None, limit_products: int = None):
        logger.info("🚀 Запуск парсинга")

        categories = await self._get_categories()
        if limit_categories:
            categories = categories[:limit_categories]

        for i, category_url in enumerate(categories, 1):
            logger.info(f"📋 Категория {i}/{len(categories)}")

            product_links = await self._get_products_from_category(category_url)
            if limit_products:
                product_links = product_links[:limit_products]

            if not product_links:
                continue

            await self._parse_and_save_products(product_links)

    async def _get_categories(self) -> List[str]:
        main_url = 'https://www.komus.ru/katalog/c/0/?from=menu-v1-vse_kategorii'
        html = await self.start_page_scraper.scrape_page(main_url)
        return await self.start_page_parser.parse_page(html)

    async def _get_products_from_category(self, category_url: str) -> List[str]:
        return await category_parser.parse_all_category_pages(category_url)

    async def _parse_and_save_products(self, product_links: List[str]):
        async with get_page() as page:
            for i, product_url in enumerate(product_links, 1):
                try:
                    logger.info(f"🔍 Товар {i}/{len(product_links)}")

                    url_with_tab = self.product_scraper.add_specifications_tab(product_url)
                    await page.goto(url_with_tab, wait_until='domcontentloaded', timeout=15000)
                    await asyncio.sleep(3)

                    parser = KomusParser(product_url)
                    product = await parser.parse_page(page)

                    await self.product_repository.save_product(product)

                except Exception as e:
                    logger.error(f"❌ Ошибка товара {i}: {e}")