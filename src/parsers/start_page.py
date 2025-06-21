import asyncio
from typing import List, Callable, Optional, Set
from bs4 import BeautifulSoup
import logging

from src.core.settings import settings
from src.parsers.base_parser import BaseParser
from src.services.state_manager import ParserState

logger = logging.getLogger(__name__)


class StartPageParser(BaseParser):
    """Парсер главной страницы с рекурсивным обходом категорий и поддержкой состояния"""

    def __init__(self):
        self.visited = set()
        self.processed_count = 0
        self.state = None

    async def parse_page(self, page) -> List[str]:
        """Старый метод для совместимости - не используется"""
        return []

    async def parse_and_process(self, page, process_category_func: Callable,
                                limit_categories: Optional[int] = None,
                                state: Optional[ParserState] = None) -> int:
        """Рекурсивно находит и сразу обрабатывает категории с товарами"""
        self.state = state
        self.processed_count = state.total_categories_processed if state else 0
        self.visited = set(state.visited_urls) if state else set()
        self.limit_categories = limit_categories
        self.process_category = process_category_func

        # Начинаем с главной страницы категорий
        categories_url = 'https://www.komus.ru/katalog/c/0/?from=menu-v1-vse_kategorii'

        # Получаем основные категории
        html = await self._get_page_html(page, categories_url)
        main_categories = self._extract_main_categories(html)

        logger.info(f"📂 Найдено основных категорий: {len(main_categories)}")

        # Если есть состояние, начинаем с сохраненного индекса
        start_index = state.current_main_category_index if state else 0

        if start_index > 0:
            logger.info(f"📌 Продолжаем с категории #{start_index + 1}")

        # Рекурсивно обходим каждую категорию
        for i in range(start_index, len(main_categories)):
            category_url = main_categories[i]

            # Обновляем текущий индекс в состоянии
            if self.state:
                self.state.current_main_category_index = i

            if self.limit_categories and self.processed_count >= self.limit_categories:
                logger.info(f"⚠️ Достигнут лимит категорий: {self.limit_categories}")
                break

            logger.info(f"\n{'=' * 80}")
            logger.info(f"📁 Основная категория {i + 1}/{len(main_categories)}")
            logger.info(f"{'=' * 80}")

            await self._process_category_recursive(page, category_url)

        return self.processed_count

    async def _process_category_recursive(self, page, category_url: str, level: int = 0):
        """Рекурсивная обработка категории"""
        if category_url in self.visited:
            return

        self.visited.add(category_url)

        # Обновляем состояние
        if self.state:
            self.state.visited_urls = list(self.visited)

        indent = "  " * level

        try:
            logger.info(f"{indent}🔍 Проверяем: {category_url}")

            # Загружаем страницу
            await page.goto(category_url, wait_until='domcontentloaded', timeout=settings.page_timeout)
            await asyncio.sleep(settings.page_load_delay)

            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')

            # Проверяем наличие товаров
            if self._has_products(soup):
                # Это конечная категория - сразу обрабатываем
                logger.info(f"{indent}✅ Найдена категория с товарами!")

                # Проверяем, не обработана ли уже эта категория
                if self.state and category_url in self.state.processed_categories:
                    logger.info(f"{indent}⏭️ Категория уже обработана, пропускаем")
                    return

                # Проверяем лимит
                if self.limit_categories and self.processed_count >= self.limit_categories:
                    return

                self.processed_count += 1

                # Вызываем функцию обработки категории
                await self.process_category(page, category_url, self.processed_count)

                # Добавляем в обработанные
                if self.state:
                    self.state.processed_categories.append(category_url)
                    self.state.total_categories_processed = self.processed_count

                return

            # Если товаров нет, ищем подкатегории
            subcategories = self._extract_subcategories(soup)

            if subcategories:
                logger.info(f"{indent}📂 Найдено подкатегорий: {len(subcategories)}")

                for subcat_url in subcategories:
                    if self.limit_categories and self.processed_count >= self.limit_categories:
                        break
                    await self._process_category_recursive(page, subcat_url, level + 1)

        except Exception as e:
            logger.error(f"{indent}❌ Ошибка при обработке {category_url}: {e}")

    def _has_products(self, soup: BeautifulSoup) -> bool:
        """Проверяет наличие товаров на странице"""
        return bool(soup.find('div', class_='product-plain') or
                    soup.find('a', class_='product-plain__name'))

    def _extract_main_categories(self, html: str) -> List[str]:
        """Извлекает ссылки на основные категории"""
        soup = BeautifulSoup(html, 'html.parser')
        categories = []

        for link in soup.find_all('a', class_='categories__name'):
            href = link.get('href', '')
            if href:
                full_url = settings.base_url.rstrip('/') + href if href.startswith('/') else href
                categories.append(full_url)

        return categories

    def _extract_subcategories(self, soup: BeautifulSoup) -> List[str]:
        """Извлекает подкатегории со страницы"""
        subcategories = []

        # Ищем все возможные ссылки на подкатегории
        for link in soup.find_all('a'):
            href = link.get('href', '')
            classes = link.get('class', [])

            # Проверяем, что это ссылка на категорию
            if (href and '/katalog/' in href and
                    any(c in str(classes) for c in ['categories', 'category'])):

                full_url = settings.base_url.rstrip('/') + href if href.startswith('/') else href

                # Избегаем дубликатов и уже посещенных
                if full_url not in self.visited and full_url not in subcategories:
                    subcategories.append(full_url)

        return subcategories

    async def _get_page_html(self, page, url: str) -> str:
        """Получение HTML страницы"""
        await page.goto(url, wait_until='domcontentloaded', timeout=settings.page_timeout)
        await asyncio.sleep(settings.page_load_delay)
        return await page.content()