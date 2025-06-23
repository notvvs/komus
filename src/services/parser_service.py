import asyncio
import logging
from typing import List

from src.core.settings import settings
from src.parsers.start_page import StartPageParser
from src.parsers.category import CategoryParser
from src.parsers.product_feature import KomusParser
from src.repository.mongo_client import mongo_client
from src.repository.repository import ProductRepository
from src.services.state_manager import ParserStateManager, ParserState

logger = logging.getLogger(__name__)


class KomusParserService:
    """Основной сервис парсинга Komus с полной миграцией на httpx + API"""

    def __init__(self):
        self.start_page_parser = StartPageParser()
        self.category_parser = CategoryParser()
        self.limit_products = None
        self.total_products_processed = 0
        self.state_manager = ParserStateManager(use_mongodb=True)
        self.state = None
        self.save_state_interval = 5  # Сохранять состояние каждые 5 категорий

    async def __aenter__(self):
        await mongo_client.connect()
        self.product_repository = ProductRepository()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await mongo_client.disconnect()

    async def run_parsing(self, limit_categories: int = None, limit_products: int = None, resume: bool = True):
        """Основной метод запуска парсинга с полной миграцией на httpx + API"""
        logger.info("Starting Komus parsing with full httpx + API migration")
        logger.info("🚀 Using API for product parsing - faster and more reliable!")

        self.limit_products = limit_products

        # Загружаем сохраненное состояние если нужно
        if resume:
            saved_state = await self.state_manager.load_state()
            if saved_state:
                self.state = ParserState.from_dict(saved_state)
                self.total_products_processed = self.state.total_products_processed

                logger.info("Found saved state:")
                logger.info(f"  - Processed categories: {self.state.total_categories_processed}")
                logger.info(f"  - Processed products: {self.state.total_products_processed}")
                logger.info(f"  - Started: {self.state.start_time}")

                # 5 секунд таймаут перед продолжением
                logger.info("Resuming in 5 seconds...")
                await asyncio.sleep(5)
                logger.info("Resuming parsing...")
            else:
                logger.info("Starting new parsing session")
                self.state = ParserState()
        else:
            self.state = ParserState()

        try:
            # Запускаем рекурсивный обход с немедленной обработкой
            # Полностью на httpx + API - максимальная производительность
            processed_categories = await self.start_page_parser.parse_and_process(
                self._process_category,
                limit_categories,
                self.state
            )

            logger.info("Parsing completed successfully")
            logger.info(f"Processed categories: {processed_categories}")
            logger.info(f"Processed products: {self.total_products_processed}")

            # Удаляем состояние после успешного завершения
            await self.state_manager.clear_state()
            logger.info("State cleared")

        except KeyboardInterrupt:
            logger.warning("Parsing interrupted by user")
            await self._save_current_state()
            logger.info("State saved")
            raise
        except Exception as e:
            logger.error(f"Critical error: {e}")
            await self._save_current_state()
            logger.info("State saved")
            raise

    async def _process_category(self, category_url: str, category_number: int):
        """Обработка одной категории с товарами"""
        logger.info(f"Processing category #{category_number}: {category_url}")

        try:
            # Получаем ссылки на товары через httpx
            product_links = await self.category_parser.parse_page(category_url)

            if self.limit_products:
                product_links = product_links[:self.limit_products]

            if not product_links:
                logger.warning("No products found in category")
                return

            logger.info(f"Found products: {len(product_links)}")

            # Обрабатываем товары через API (самый быстрый способ)
            await self._process_products_via_api(product_links)

            self.total_products_processed += len(product_links)
            self.state.total_products_processed = self.total_products_processed

            # Периодически сохраняем состояние
            if category_number % self.save_state_interval == 0:
                await self._save_current_state()

        except Exception as e:
            logger.error(f"Error processing category: {e}")
            # Сохраняем состояние при ошибке
            await self._save_current_state()

    async def _process_products_via_api(self, product_links: List[str]):
        """Обработка списка товаров через API (максимальная скорость)"""
        logger.info(f"Processing {len(product_links)} products via API")

        for i, product_url in enumerate(product_links, 1):
            try:
                logger.info(f"Processing product {i}/{len(product_links)}: {product_url}")

                # Извлекаем ID товара из URL
                product_id = self._extract_product_id_from_url(product_url)

                if not product_id:
                    logger.warning(f"Could not extract product ID from URL: {product_url}")
                    continue

                # Создаем API парсер для товара
                product_parser = KomusParser(product_id=product_id, product_url=product_url)

                # Парсим товар через API (намного быстрее HTML)
                product = await product_parser.parse_page()

                # Проверяем успешность парсинга
                if product.title == "Нет данных" or product.title.startswith("Ошибка"):
                    logger.warning(f"Failed to parse product {product_id}: {product.title}")
                    continue

                # Сохраняем товар в БД
                await self.product_repository.save_product(product)

                # Небольшая задержка между товарами (API может выдержать более высокую нагрузку)
                await asyncio.sleep(0.5)  # Уменьшена с 1 секунды для API

            except Exception as e:
                logger.error(f"Error processing product {i} ({product_url}): {e}")
                continue

    def _extract_product_id_from_url(self, url: str) -> str:
        """Извлечение ID товара из URL"""
        import re
        match = re.search(r'/p/(\d+)/', url)
        return match.group(1) if match else ""

    async def _save_current_state(self):
        """Сохраняет текущее состояние"""
        await self.state_manager.save_state(self.state.to_dict())
        logger.info(
            f"State saved (categories: {self.state.total_categories_processed}, products: {self.state.total_products_processed})")