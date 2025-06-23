import asyncio
import math
from typing import List
from bs4 import BeautifulSoup
import logging

from src.core.settings import settings
from src.parsers.base_parser import BaseParser
from src.utils.http_requests import make_request, refresh_session_on_503

logger = logging.getLogger(__name__)


class CategoryParser(BaseParser):
    """Интегрированный парсер категорий - объединяет scraping и parsing, использующий httpx"""

    def __init__(self):
        pass  # Убираем локальную сессию - используем session manager

    async def parse_page(self, category_url: str) -> List[str]:
        """Главный метод - возвращает все ссылки на товары из категории"""
        all_product_links = []

        try:
            category_page_urls = await self._get_category_pages(category_url)

            logger.info(f"Found {len(category_page_urls)} pages in category")

            for i, page_url in enumerate(category_page_urls, 1):
                logger.info(f"Processing page {i}/{len(category_page_urls)}: {page_url}")
                product_links = await self._get_product_links_from_page(page_url)
                all_product_links.extend(product_links)

                # Небольшая задержка между страницами
                if i < len(category_page_urls):
                    await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error parsing category {category_url}: {e}")

        return all_product_links

    async def _get_category_pages(self, category_url: str) -> List[str]:
        """Получение ссылок на все страницы категории"""
        try:
            # Получаем HTML страницы через httpx
            html = await self._get_page_html(category_url)

            if not html:
                logger.error(f"Failed to get HTML for {category_url}")
                return [category_url]  # Возвращаем хотя бы исходную страницу

            soup = BeautifulSoup(html, 'html.parser')
            total_pages = self._calculate_pages_count(soup)

            logger.info(f"Category has {total_pages} pages")

            base_url = category_url.split('?')[0].rstrip('/')
            category_pages = []

            for page_number in range(total_pages):
                page_url = f"{base_url}/f/stocklevelstatus=instock/?page={page_number}"
                category_pages.append(page_url)

            return category_pages

        except Exception as e:
            logger.error(f"Error getting category pages for {category_url}: {e}")
            return [category_url]  # Fallback - возвращаем исходную страницу

    async def _get_product_links_from_page(self, page_url: str) -> List[str]:
        """Получение ссылок на товары с одной страницы"""
        try:
            # Получаем HTML страницы через httpx
            html = await self._get_page_html(page_url)

            if not html:
                logger.error(f"Failed to get HTML for {page_url}")
                return []

            return self._parse_product_links_from_html(html)

        except Exception as e:
            logger.error(f"Error getting product links from {page_url}: {e}")
            return []

    async def _get_page_html(self, url: str) -> str:
        """Получение HTML страницы через httpx"""
        try:
            # Используем session manager - автоматическое управление сессией
            response = await make_request(
                url=url,
                method="GET",
                max_retries=3
            )

            if response.status_code == 200:
                # Задержки как в оригинале
                await asyncio.sleep(settings.page_load_delay)
                await asyncio.sleep(0.5)  # Дополнительная задержка
                return response.text
            else:
                logger.error(f"HTTP {response.status_code} for {url}")
                return ""

        except Exception as e:
            logger.error(f"Request error for {url}: {e}")
            return ""

    def _parse_product_links_from_html(self, html: str) -> List[str]:
        """Парсинг ссылок на товары из HTML"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            product_links = []

            # Ищем ссылки с классом product-plain__name js-product-variant-name
            links = soup.find_all('a', class_='product-plain__name js-product-variant-name')

            for link in links:
                href = link.get('href')
                if href:
                    if href.startswith('/'):
                        href = settings.base_url.rstrip('/') + href
                    product_links.append(href)

            logger.info(f"Found {len(product_links)} product links on page")
            return product_links

        except Exception as e:
            logger.error(f"Error parsing product links from HTML: {e}")
            return []

    def _calculate_pages_count(self, soup: BeautifulSoup) -> int:
        """Вычисление количества страниц в категории"""
        try:
            # Ищем элемент с количеством товаров
            items_count_elem = soup.find('span', class_="catalog__header-sup")

            if items_count_elem:
                items_count_text = items_count_elem.get_text(strip=True)
                items_count = int(items_count_text)

                # Komus показывает 30 товаров на странице
                pages_count = math.ceil(items_count / 30)
                return max(1, pages_count)

            # Если не нашли количество товаров, возвращаем 1 страницу
            return 1

        except (ValueError, AttributeError) as e:
            logger.warning(f"Error calculating pages count: {e}")
            return 1