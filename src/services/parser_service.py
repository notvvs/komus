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
from src.services.state_manager import ParserStateManager, ParserState

logger = logging.getLogger(__name__)


class KomusParserService:
    """Основной сервис парсинга Komus с поддержкой сохранения состояния"""

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
        """Основной метод запуска парсинга с поддержкой возобновления"""
        logger.info("🚀 Запуск парсинга Komus")

        self.limit_products = limit_products

        # Загружаем сохраненное состояние если нужно
        if resume:
            saved_state = await self.state_manager.load_state()
            if saved_state:
                self.state = ParserState.from_dict(saved_state)
                self.total_products_processed = self.state.total_products_processed

                logger.info("📂 Найдено сохраненное состояние:")
                logger.info(f"  - Обработано категорий: {self.state.total_categories_processed}")
                logger.info(f"  - Обработано товаров: {self.state.total_products_processed}")
                logger.info(f"  - Начато: {self.state.start_time}")

                response = input("\n➡️ Продолжить с сохраненного места? (y/n): ")
                if response.lower() != 'y':
                    logger.info("🆕 Начинаем заново...")
                    await self.state_manager.clear_state()
                    self.state = ParserState()
                else:
                    logger.info("▶️ Продолжаем парсинг...")
            else:
                logger.info("🆕 Начинаем новый парсинг...")
                self.state = ParserState()
        else:
            self.state = ParserState()

        try:
            async with get_page() as page:
                # Запускаем рекурсивный обход с немедленной обработкой
                processed_categories = await self.start_page_parser.parse_and_process(
                    page,
                    self._process_category,
                    limit_categories,
                    self.state
                )

                logger.info("=" * 80)
                logger.info("✅ Парсинг успешно завершен!")
                logger.info(f"📂 Обработано категорий: {processed_categories}")
                logger.info(f"📦 Обработано товаров: {self.total_products_processed}")

                # Удаляем состояние после успешного завершения
                await self.state_manager.clear_state()
                logger.info("🧹 Состояние очищено")

        except KeyboardInterrupt:
            logger.warning("\n⚠️ Парсинг прерван пользователем")
            await self._save_current_state()
            logger.info("💾 Состояние сохранено. Можно продолжить позже.")
            raise
        except Exception as e:
            logger.error(f"\n❌ Критическая ошибка: {e}")
            await self._save_current_state()
            logger.info("💾 Состояние сохранено. Можно продолжить позже.")
            raise

    async def _process_category(self, page, category_url: str, category_number: int):
        """Обработка одной категории с товарами"""
        logger.info(f"\n{'=' * 60}")
        logger.info(f"🛍️ Категория #{category_number}: {category_url}")
        logger.info(f"{'=' * 60}")

        try:
            # Получаем ссылки на товары
            product_links = await self.category_parser.parse_page(page, category_url)

            if self.limit_products:
                product_links = product_links[:self.limit_products]

            if not product_links:
                logger.warning(f"⚠️ В категории не найдено товаров")
                return

            logger.info(f"🛍️ Найдено товаров: {len(product_links)}")

            # Обрабатываем товары
            await self._process_products(page, product_links)

            self.total_products_processed += len(product_links)
            self.state.total_products_processed = self.total_products_processed

            # Периодически сохраняем состояние
            if category_number % self.save_state_interval == 0:
                await self._save_current_state()

        except Exception as e:
            logger.error(f"❌ Ошибка обработки категории: {e}")
            # Сохраняем состояние при ошибке
            await self._save_current_state()

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

    async def _save_current_state(self):
        """Сохраняет текущее состояние"""
        await self.state_manager.save_state(self.state.to_dict())
        logger.info(
            f"💾 Состояние сохранено (категорий: {self.state.total_categories_processed}, товаров: {self.state.total_products_processed})")