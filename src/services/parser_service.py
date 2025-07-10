import asyncio
import logging
from typing import List

from src.parsers.start_page import StartPageParser
from src.parsers.category import CategoryParser
from src.parsers.product_feature import KomusParser
from src.repository.mongo_client import mongo_client
from src.repository.repository import ProductRepository

logger = logging.getLogger(__name__)


class KomusParserService:
    def __init__(self):
        self.start_page_parser = StartPageParser()
        self.category_parser = CategoryParser()
        self.total_products_processed = 0

    async def __aenter__(self):
        await mongo_client.connect()
        self.product_repository = ProductRepository()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await mongo_client.disconnect()

    async def run_parsing(self):
        logger.info("Starting Komus parsing")

        try:
            processed_categories = await self.start_page_parser.parse_and_process(
                self._process_category
            )

            logger.info("Parsing completed successfully")
            logger.info(f"Processed categories: {processed_categories}")
            logger.info(f"Processed products: {self.total_products_processed}")

        except KeyboardInterrupt:
            logger.warning("Parsing interrupted by user")
            raise
        except Exception as e:
            logger.error(f"Critical error: {e}")
            raise

    async def _process_category(self, category_url: str, category_number: int):
        logger.info(f"Processing category #{category_number}: {category_url}")

        try:
            product_links = await self.category_parser.parse_page(category_url)

            if not product_links:
                logger.warning("No products found in category")
                return

            logger.info(f"Found products: {len(product_links)}")
            await self._process_products(product_links)
            self.total_products_processed += len(product_links)

        except Exception as e:
            logger.error(f"Error processing category: {e}")

    async def _process_products(self, product_links: List[str]):
        for i, product_url in enumerate(product_links, 1):
            try:
                logger.info(f"Processing product {i}/{len(product_links)}")

                product_id = self._extract_product_id(product_url)
                if not product_id:
                    continue

                product_parser = KomusParser(product_id=product_id, product_url=product_url)
                product = await product_parser.parse_page()

                if not product.title.startswith("Ошибка"):
                    await self.product_repository.save_product(product)

                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Error processing product {i}: {e}")
                continue

    def _extract_product_id(self, url: str) -> str:
        import re
        match = re.search(r'/p/(\d+)/', url)
        return match.group(1) if match else ""