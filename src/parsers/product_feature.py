import asyncio
import re
import logging
from typing import List

from src.parsers.base_parser import BaseParserBrowser
from src.schemas.product import Product, Attribute, PriceInfo, SupplierOffer, Supplier

# Настройка логирования
logger = logging.getLogger(__name__)

class KomusParser(BaseParserBrowser):
    """Парсер страниц товаров Komus"""

    def __init__(self, url: str):
        self.url = url
        self.page = None

    async def parse_page(self, page) -> Product:
        """Основной метод парсинга страницы"""
        self.page = page
        logger.info(f"Начинаем парсинг: {self.url}")

        await self._scroll_page()
        product = await self._create_product()

        logger.info(f"Парсинг завершен: {product.title[:50]}...")
        return product

    async def _scroll_page(self):
        """Полный скролл страницы"""
        try:
            total_height = await self.page.evaluate("document.body.scrollHeight")

            for position in range(0, total_height, 300):
                await self.page.evaluate(f"window.scrollTo(0, {position})")
                await asyncio.sleep(0.3)

                new_height = await self.page.evaluate("document.body.scrollHeight")
                if new_height > total_height:
                    total_height = new_height

            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Ошибка скролла: {e}")

    async def _create_product(self) -> Product:
        """Создание объекта Product"""
        return Product(
            title=await self._get_title(),
            description=await self._get_description(),
            article=await self._get_article(),
            brand=await self._get_brand(),
            country_of_origin=await self._get_country_of_origin(),
            warranty_months=await self._get_warranty_months(),
            category=await self._get_category(),
            attributes=await self._get_attributes(),
            suppliers=[await self._create_supplier()]
        )

    async def _get_title(self) -> str:
        """Название товара"""
        try:
            title_elem = self.page.locator('h1').first
            if await title_elem.count() > 0:
                return await title_elem.text_content()
        except:
            pass
        return "Нет данных"

    async def _get_description(self) -> str:
        """Описание товара"""
        try:
            desc_elem = self.page.locator('.product-info-details__description')
            if await desc_elem.count() > 0:
                return await desc_elem.text_content()
        except:
            pass
        return "Нет данных"

    async def _get_article(self) -> str:
        """Артикул товара"""
        match = re.search(r'/p/(\d+)/', self.url)
        return match.group(1) if match else "Нет данных"

    async def _get_brand(self) -> str:
        """Торговая марка"""
        try:
            brand_elem = self.page.locator('.product-info-specifications__common-link .v-link')
            if await brand_elem.count() > 0:
                return await brand_elem.text_content()

            specs = await self._get_attributes_dict()
            for key in ['Торговая марка', 'Бренд', 'Производитель', 'Марка']:
                if key in specs:
                    return specs[key]
        except:
            pass
        return "Нет данных"

    async def _get_category(self) -> str:
        """Категория - предпоследнее значение из breadcrumbs"""
        try:
            breadcrumbs = self.page.locator('.breadcrumbs__item a, .breadcrumb a, nav a')
            if await breadcrumbs.count() > 0:
                categories = []
                for i in range(await breadcrumbs.count()):
                    text = await breadcrumbs.nth(i).text_content()
                    if text and text.strip() and text.strip().lower() != 'главная':
                        categories.append(text.strip())

                if len(categories) >= 2:
                    return categories[-2]
                elif len(categories) == 1:
                    return categories[0]
        except:
            pass
        return "Нет данных"

    async def _get_country_of_origin(self) -> str:
        """Страна происхождения"""
        try:
            specs = await self._get_attributes_dict()
            for key in ['Страна происхождения', 'Страна-производитель', 'Страна изготовления']:
                if key in specs:
                    return specs[key]
        except:
            pass
        return "Нет данных"

    async def _get_warranty_months(self) -> str:
        """Гарантийный срок"""
        try:
            specs = await self._get_attributes_dict()
            for key in ['Гарантийный срок', 'Гарантия', 'Срок гарантии']:
                if key in specs:
                    return specs[key]
        except:
            pass
        return "Нет данных"

    async def _get_attributes_dict(self) -> dict:
        """Характеристики в виде словаря"""
        try:
            specifications = {}
            spec_items = self.page.locator('.product-info-specifications__item')

            for i in range(await spec_items.count()):
                item = spec_items.nth(i)
                key_elem = item.locator('.product-info-specifications__key')
                value_elem = item.locator('.product-info-specifications-value, .product-info-specifications__value')

                if await key_elem.count() > 0 and await value_elem.count() > 0:
                    key = await key_elem.text_content()
                    value = await value_elem.text_content()

                    if key and value:
                        key = re.sub(r'\s+', ' ', key.strip())
                        value = re.sub(r'\s+', ' ', value.strip())
                        if key and value:
                            specifications[key] = value

            return specifications
        except:
            return {}

    async def _get_attributes(self) -> List[Attribute]:
        """Характеристики в виде списка"""
        specs_dict = await self._get_attributes_dict()
        return [Attribute(attr_name=key, attr_value=value) for key, value in specs_dict.items()]

    async def _get_price_info(self) -> List[PriceInfo]:
        """Информация о ценах"""
        try:
            main_price = None
            old_price = None

            # Основная цена
            main_price_elem = self.page.locator('.js-current-price')
            if await main_price_elem.count() > 0:
                price_text = await main_price_elem.text_content()
                if price_text:
                    clean_price = re.sub(r'[^\d,.]', '', price_text.strip())
                    try:
                        main_price = float(clean_price.replace(',', '.'))
                    except ValueError:
                        pass

            # Старая цена
            old_price_elem = self.page.locator('.product-price__old-price span').first
            if await old_price_elem.count() > 0:
                old_price_text = await old_price_elem.text_content()
                if old_price_text:
                    clean_old_price = re.sub(r'[^\d,.]', '', old_price_text.replace('\u00a0', ''))
                    try:
                        old_price = float(clean_old_price.replace(',', '.'))
                    except ValueError:
                        pass

            # Создаем PriceInfo
            if main_price and main_price > 0:
                discount = 0
                if old_price and old_price > main_price:
                    discount = round(((old_price - main_price) / old_price) * 100, 2)

                return [PriceInfo(qnt=1, discount=discount, price=main_price)]

            return [PriceInfo(qnt=1, discount=0, price=0)]

        except Exception as e:
            logger.error(f"Ошибка извлечения цены: {e}")
            return [PriceInfo(qnt=1, discount=0, price=0)]

    async def _get_stock_info(self) -> str:
        """Наличие - только количество"""
        try:
            stock_count_elem = self.page.locator('.js-product-stock-count')
            if await stock_count_elem.count() > 0:
                stock_text = await stock_count_elem.text_content()
                if stock_text and stock_text.strip():
                    return stock_text.strip().replace('\u00a0', ' ')
            return "Нет данных"
        except:
            return "Нет данных"

    async def _get_delivery_info(self) -> str:
        """Информация о доставке"""
        try:
            delivery_elem = self.page.locator('.product-status__message--green span')
            if await delivery_elem.count() > 0:
                delivery_text = await delivery_elem.text_content()
                if delivery_text and delivery_text.strip():
                    return delivery_text.strip()
            return "Нет данных"
        except:
            return "Нет данных"

    async def _get_package_info(self) -> str:
        """Информация об упаковке"""
        try:
            package_elem = self.page.locator('.transport-package__description').first
            if await package_elem.count() > 0:
                package_text = await package_elem.text_content()
                if package_text and package_text.strip():
                    return f"В коробе {package_text.strip()}"
            return "Нет данных"
        except:
            return "Нет данных"

    async def _create_supplier_offer(self) -> SupplierOffer:
        """Создание предложения поставщика"""
        return SupplierOffer(
            price=await self._get_price_info(),
            stock=await self._get_stock_info(),
            delivery_time=await self._get_delivery_info(),
            package_info=await self._get_package_info(),
            purchase_url=self.url
        )

    async def _create_supplier(self) -> Supplier:
        """Создание поставщика"""
        offer = await self._create_supplier_offer()
        return Supplier(supplier_offers=[offer])


