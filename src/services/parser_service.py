import asyncio
import logging
from typing import List

from src.parsers.start_page import StartPageParser
from src.parsers.category import CategoryParser
from src.parsers.product_feature import KomusParser
from src.repository.mongo_client import mongo_client
from src.repository.repository import ProductRepository
from src.scrapers.start_page import StartPageScraper
from src.utils.create_driver import get_page

logger = logging.getLogger(__name__)


class KomusParserService:
    def __init__(self):
        self.start_page_scraper = StartPageScraper()
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
        logger.info("🚀 Запуск парсинга через Playwright")

        async with get_page() as page:
            # Получаем категории
            categories = await self._get_categories(page)
            if limit_categories:
                categories = categories[:limit_categories]

            logger.info(f"📂 Найдено категорий: {len(categories)}")

            for i, category_url in enumerate(categories, 1):
                logger.info(f"📋 Категория {i}/{len(categories)}: {category_url}")

                try:
                    # Получаем товары из категории
                    product_links = await self._get_products_from_category(page, category_url)
                    if limit_products:
                        product_links = product_links[:limit_products]

                    if not product_links:
                        logger.warning(f"⚠️ В категории {i} не найдено товаров")
                        continue

                    logger.info(f"🛍️ Найдено товаров: {len(product_links)}")

                    # Парсим и сохраняем товары
                    await self._parse_and_save_products(page, product_links)

                except Exception as e:
                    logger.error(f"❌ Ошибка обработки категории {i}: {e}")
                    continue

    async def _get_categories(self, page) -> List[str]:
        """Получение списка категорий"""
        main_url = 'https://www.komus.ru/katalog/c/0/?from=menu-v1-vse_kategorii'
        html = await self.start_page_scraper.scrape_page(page, main_url)
        return await self.start_page_parser.parse_page(html)

    async def _get_products_from_category(self, page, category_url: str) -> List[str]:
        """Получение товаров из категории"""
        return await self.category_parser.parse_all_category_pages(page, category_url)

    async def _parse_and_save_products(self, page, product_links: List[str]):
        """Парсинг и сохранение товаров"""
        for i, product_url in enumerate(product_links, 1):
            try:
                logger.info(f"🔍 Товар {i}/{len(product_links)}")

                # Добавляем табы спецификаций к URL
                url_with_tab = self._add_specifications_tab(product_url)

                # Переходим на страницу товара
                await page.goto(url_with_tab, wait_until='domcontentloaded', timeout=15000)
                await asyncio.sleep(3)

                # Парсим товар
                parser = KomusParser(product_url)
                product = await parser.parse_page(page)

                # Сохраняем в базу
                await self.product_repository.save_product(product)

            except Exception as e:
                logger.error(f"❌ Ошибка товара {i}: {e}")
                continue

    def _add_specifications_tab(self, url: str) -> str:
        """Добавление табов спецификаций к URL"""
        if '?' in url:
            return url + '&tabId=specifications'
        else:
            return url + '?tabId=specifications'