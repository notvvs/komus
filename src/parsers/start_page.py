import asyncio
from typing import List, Callable, Optional
from bs4 import BeautifulSoup
import logging

from src.core.settings import settings
from src.parsers.base_parser import BaseParser
from src.services.state_manager import ParserState
from src.utils.http_requests import make_request, refresh_session_on_503

logger = logging.getLogger(__name__)


class StartPageParser(BaseParser):
    """Парсер с рекурсивным обходом категорий с классом categories__name, использующий httpx"""

    def __init__(self):
        self.visited = set()
        self.processed_count = 0
        self.state = None
        self.session_data = None  # Кэшируем cookies и headers

    async def parse_page(self, *args, **kwargs) -> List[str]:
        """Старый метод для совместимости - не используется"""
        return []

    async def parse_and_process(self, process_category_func: Callable,
                                limit_categories: Optional[int] = None,
                                state: Optional[ParserState] = None) -> int:
        """Рекурсивно находит и обрабатывает категории с классом categories__name"""
        self.state = state
        self.processed_count = state.total_categories_processed if state else 0
        self.visited = set(state.visited_urls) if state else set()
        self.limit_categories = limit_categories
        self.process_category = process_category_func

        # Получаем свежую сессию в начале
        logger.info("🔄 Инициализация сессии...")
        self.session_data = await refresh_session_on_503()

        # Начинаем с главной страницы категорий
        categories_url = 'https://www.komus.ru/katalog/c/0/?from=menu-v1-vse_kategorii'

        # Получаем основные категории
        html = await self._get_page_html(categories_url)
        main_categories = self._extract_categories_with_class(html)

        logger.info(f"Found main categories: {len(main_categories)}")

        # Если есть состояние, начинаем с сохраненного индекса
        start_index = state.current_main_category_index if state else 0

        if start_index > 0:
            logger.info(f"Continuing from category #{start_index + 1}")

        # Рекурсивно обходим каждую категорию
        for i in range(start_index, len(main_categories)):
            category_url = main_categories[i]

            # Обновляем текущий индекс в состоянии
            if self.state:
                self.state.current_main_category_index = i

            if self.limit_categories and self.processed_count >= self.limit_categories:
                logger.info(f"Category limit reached: {self.limit_categories}")
                break

            logger.info(f"Main category {i + 1}/{len(main_categories)}")

            await self._process_category_recursive(category_url)

        return self.processed_count

    async def _process_category_recursive(self, category_url: str, level: int = 0):
        """Рекурсивная обработка категории"""
        if category_url in self.visited:
            return

        self.visited.add(category_url)

        # Обновляем состояние
        if self.state:
            self.state.visited_urls = list(self.visited)

        indent = "  " * level

        try:
            logger.info(f"{indent}Checking: {category_url}")

            # Загружаем страницу через httpx
            html = await self._get_page_html(category_url)
            soup = BeautifulSoup(html, 'html.parser')

            # Проверяем наличие товаров
            if self._has_products(soup):
                # Это конечная категория - сразу обрабатываем
                logger.info(f"{indent}Found category with products")

                # Проверяем, не обработана ли уже эта категория
                if self.state and category_url in self.state.processed_categories:
                    logger.info(f"{indent}Category already processed, skipping")
                    return

                # Проверяем лимит
                if self.limit_categories and self.processed_count >= self.limit_categories:
                    return

                self.processed_count += 1

                # Вызываем функцию обработки категории
                await self.process_category(category_url, self.processed_count)

                # Добавляем в обработанные
                if self.state:
                    self.state.processed_categories.append(category_url)
                    self.state.total_categories_processed = self.processed_count

                return

            # Если товаров нет, ищем подкатегории с классом categories__name
            subcategories = self._extract_categories_with_class(html)

            if subcategories:
                logger.info(f"{indent}Found subcategories: {len(subcategories)}")

                for subcat_url in subcategories:
                    if self.limit_categories and self.processed_count >= self.limit_categories:
                        break

                    # Пропускаем уже посещенные URL
                    if subcat_url not in self.visited:
                        await self._process_category_recursive(subcat_url, level + 1)
            else:
                logger.info(f"{indent}No subcategories found")

        except Exception as e:
            logger.error(f"{indent}Error processing {category_url}: {e}")

            # При ошибке пытаемся обновить сессию
            if "503" in str(e) or "Forbidden" in str(e):
                logger.warning(f"{indent}Session issue detected, refreshing session...")
                self.session_data = await refresh_session_on_503()

    async def _get_page_html(self, url: str) -> str:
        """Получение HTML страницы через httpx"""
        try:
            # Используем session manager - автоматическое управление сессией
            response = await make_request(
                url=url,
                method="GET",
                max_retries=3
            )

            # При успешном запросе обновляем сессию данными
            if response.status_code == 200:
                # Дополнительная задержка как в оригинале
                await asyncio.sleep(settings.page_load_delay)
                await asyncio.sleep(0.5)  # Дополнительная задержка
                return response.text
            else:
                logger.error(f"HTTP {response.status_code} for {url}")
                return ""

        except Exception as e:
            logger.error(f"Request error for {url}: {e}")
            return ""

    def _has_products(self, soup: BeautifulSoup) -> bool:
        """Проверяет наличие товаров на странице"""
        return bool(soup.find('div', class_='product-plain') or
                    soup.find('a', class_='product-plain__name'))

    def _extract_categories_with_class(self, html: str) -> List[str]:
        """Извлекает ссылки ТОЛЬКО на категории с классом categories__name"""
        if isinstance(html, str):
            soup = BeautifulSoup(html, 'html.parser')
        else:
            soup = html

        categories = []

        # Ищем ТОЛЬКО элементы с классом categories__name
        category_links = soup.find_all('a', class_='categories__name')

        for link in category_links:
            href = link.get('href', '')
            if href and '/katalog/' in href:
                # Формируем полный URL
                full_url = settings.base_url.rstrip('/') + href if href.startswith('/') else href
                categories.append(full_url)

        return categories