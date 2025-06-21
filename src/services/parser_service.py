import asyncio
import logging
from typing import List

from src.core.settings import settings
from src.parsers.start_page import StartPageParser
from src.parsers.category import CategoryParser
from src.parsers.product_feature import KomusParser
from src.repository.mongo_client import mongo_client
from src.repository.repository import ProductRepository
from src.utils.create_driver import get_page

logger = logging.getLogger(__name__)


class KomusParserService:
    """Основной сервис парсинга Komus с настройками из .env"""

    def __init__(self):
        self.start_page_parser = StartPageParser()
        self.category_parser = CategoryParser()

    async def __aenter__(self):
        await mongo_client.connect()
        self.product_repository = ProductRepository()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await mongo_client.disconnect()

    async def run_parsing(self, limit_categories: int = None, limit_products: int = None):
        """Основной метод запуска парсинга"""
        logger.info("🚀 Запуск парсинга Komus")

        async with get_page() as page:
            categories = await self.start_page_parser.parse_page(page)
            if limit_categories:
                categories = categories[:limit_categories]

            logger.info(f"📂 Найдено категорий: {len(categories)}")

            for i, category_url in enumerate(categories, 1):
                logger.info(f"📋 Обрабатываем категорию {i}/{len(categories)}: {category_url}")

                try:
                    product_links = await self.category_parser.parse_page(page, category_url)
                    if limit_products:
                        product_links = product_links[:limit_products]

                    if not product_links:
                        logger.warning(f"⚠️ В категории {i} не найдено товаров")
                        continue

                    logger.info(f"🛍️ Найдено товаров: {len(product_links)}")

                    await self._process_products(page, product_links)

                except Exception as e:
                    logger.error(f"❌ Ошибка обработки категории {i}: {e}")
                    continue

        logger.info("✅ Парсинг завершен")

    async def _process_products(self, page, product_links: List[str]):
        """Обработка списка товаров"""
        for i, product_url in enumerate(product_links, 1):
            try:
                logger.info(f"🔍 Обрабатываем товар {i}/{len(product_links)}")

                url_with_specs = self._add_specifications_tab(product_url)

                await page.goto(url_with_specs, wait_until='domcontentloaded', timeout=settings.page_timeout)
                await asyncio.sleep(settings.product_load_delay)

                product_parser = KomusParser(product_url)
                product = await product_parser.parse_page(page)

                await self.product_repository.save_product(product)

            except Exception as e:
                logger.error(f"❌ Ошибка обработки товара {i}: {e}")
                continue

    def _add_specifications_tab(self, url: str) -> str:
        """Добавление параметра для открытия вкладки характеристик"""
        if '?' in url:
            return url + '&tabId=specifications'
        else:
            return url + '?tabId=specifications'