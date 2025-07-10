# src/parsers/product_feature.py
import re
import html
import logging
from typing import List, Optional, Dict, Any, Tuple
import json
import httpx

from src.parsers.base_parser import BaseParser
from src.schemas.product import Product, Attribute, PriceInfo, SupplierOffer, Supplier

logger = logging.getLogger(__name__)


def clean_description(description: str) -> str:
    """Очищает описание товара от HTML тегов и форматирования"""
    if not description or description == "Нет данных":
        return "Нет данных"

    cleaned = html.unescape(description)

    html_entities = {
        '&deg;': '°', '&times;': '×', '&nbsp;': ' ',
        '&laquo;': '«', '&raquo;': '»', '&mdash;': '—'
    }

    for entity, symbol in html_entities.items():
        cleaned = cleaned.replace(entity, symbol)

    cleaned = re.sub(r'<[Bb][Rr]\s*/?>', '\n', cleaned)
    cleaned = re.sub(r'<[^>]*>', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = re.sub(r'\n\s*\n', '\n\n', cleaned)

    lines = [line.strip() for line in cleaned.split('\n')]
    cleaned = '\n'.join(line for line in lines if line)

    return cleaned.strip() if cleaned.strip() else "Нет данных"


class KomusParser(BaseParser):
    def __init__(self, product_id: str = None, product_url: str = None):
        self.product_id = product_id
        self.product_url = product_url
        self.price_data = None
        self.product_data = None

        if not self.product_id and self.product_url:
            self.product_id = self._extract_product_id(self.product_url)

    def _extract_product_id(self, url: str) -> str:
        match = re.search(r'/p/(\d+)/', url)
        return match.group(1) if match else ""

    async def parse_page(self, product_id: str = None, product_url: str = None) -> Product:
        if product_id:
            self.product_id = product_id
        elif product_url:
            self.product_url = product_url
            self.product_id = self._extract_product_id(product_url)

        if not self.product_id:
            return self._create_error_product("Не удалось извлечь ID товара")

        try:
            # Получаем данные из двух API
            self.price_data, self.product_data = await self._get_combined_api_data()

            if not self.price_data and not self.product_data:
                return self._create_error_product("Не удалось получить данные через API")

            return await self._create_product()

        except Exception as e:
            logger.error(f"Error parsing product {self.product_id}: {e}")
            return self._create_error_product(f"Ошибка парсинга: {str(e)}")

    async def _get_combined_api_data(self) -> Tuple[Optional[Dict], Optional[Dict]]:
        """Получает данные из двух API запросов"""
        try:
            # Базовые заголовки
            base_headers = {
                'accept': 'application/json',
                'accept-language': 'ru,en;q=0.9',
                'sec-ch-ua': '"Chromium";v="136", "YaBrowser";v="25.6", "Not.A/Brand";v="99", "Yowser";v="2.5"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"macOS"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 YaBrowser/25.6.0.0 Safari/537.36',
                'x-requested-with': 'XMLHttpRequest'
            }

            if self.product_url:
                base_headers['referer'] = self.product_url

            async with httpx.AsyncClient(timeout=30.0) as client:
                # Запрос 1: PriceBlock API (POST)
                price_data = await self._get_price_block_data(client, base_headers)

                # Запрос 2: Product API (GET)
                product_data = await self._get_product_details_data(client, base_headers)

                return price_data, product_data

        except Exception as e:
            logger.error(f"Error getting combined API data: {e}")
            return None, None

    async def _get_price_block_data(self, client: httpx.AsyncClient, base_headers: Dict) -> Optional[Dict]:
        """Получает данные о цене и наличии"""
        try:
            price_url = f"https://www.komus.ru/api/priceBlock/{self.product_id}"

            headers = base_headers.copy()
            headers.update({
                'content-length': '0',
                'origin': 'https://www.komus.ru',
                'priority': 'u=1, i'
            })

            response = await client.post(price_url, headers=headers)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"PriceBlock API failed: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error getting price block data: {e}")
            return None

    async def _get_product_details_data(self, client: httpx.AsyncClient, base_headers: Dict) -> Optional[Dict]:
        """Получает детальные характеристики товара"""
        try:
            product_url = f"https://www.komus.ru/api/product/{self.product_id}"

            params = {
                'fields': 'featureGroups,productSet,trademark,name,description,code,price,stock,images,categories'
            }

            headers = base_headers.copy()
            headers['priority'] = 'u=1, i'

            response = await client.get(product_url, params=params, headers=headers)

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Product API failed: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error getting product details: {e}")
            return None

    async def _create_product(self) -> Product:
        return Product(
            title=self._get_title(),
            description=self._get_description(),
            article=self.product_id,
            brand=self._get_brand(),
            country_of_origin=self._get_country(),
            warranty_months=self._get_warranty(),
            category=self._get_category(),
            attributes=self._get_attributes(),
            suppliers=[self._create_supplier()]
        )

    def _create_error_product(self, error_msg: str) -> Product:
        return Product(
            title=f"Ошибка: {error_msg}",
            description="Произошла ошибка при извлечении данных товара",
            article=self.product_id or "unknown",
            brand="Неизвестно",
            country_of_origin="Нет данных",
            warranty_months="Нет данных",
            category="Нет данных",
            attributes=[],
            suppliers=[]
        )

    def _get_title(self) -> str:
        # Сначала пытаемся из product_data
        if self.product_data and 'name' in self.product_data:
            return self.product_data['name']

        # Потом из price_data
        if self.price_data and 'payload' in self.price_data:
            product = self.price_data['payload'].get('product', {})
            if 'name' in product:
                return product['name']

        return "Нет данных"

    def _get_description(self) -> str:
        if self.product_data:
            raw_description = ""
            if 'description' in self.product_data:
                raw_description = self.product_data['description']
            elif 'shortDescription' in self.product_data:
                raw_description = self.product_data['shortDescription']

            if raw_description:
                return clean_description(raw_description)

        return "Нет данных"

    def _get_brand(self) -> str:
        # Из product_data trademark
        if self.product_data and 'trademark' in self.product_data:
            trademark = self.product_data['trademark']
            if isinstance(trademark, dict) and 'name' in trademark:
                return trademark['name']

        # Из характеристик
        attributes_dict = self._get_attributes_dict()
        brand_keys = ['Торговая марка', 'Бренд', 'Производитель', 'Марка']

        for key in brand_keys:
            if key in attributes_dict:
                return attributes_dict[key]

        return "Нет данных"

    def _get_country(self) -> str:
        attributes_dict = self._get_attributes_dict()
        country_keys = ['Страна происхождения', 'Страна-производитель', 'Страна изготовления']

        for key in country_keys:
            if key in attributes_dict:
                return attributes_dict[key]

        return "Нет данных"

    def _get_warranty(self) -> str:
        attributes_dict = self._get_attributes_dict()
        warranty_keys = ['Гарантийный срок', 'Гарантия', 'Срок гарантии']

        for key in warranty_keys:
            if key in attributes_dict:
                value = attributes_dict[key]
                if key == 'Гарантийный срок' and value.isdigit():
                    return f"{value} мес"
                return value

        return "Нет данных"

    def _get_category(self) -> str:
        # Из product_data categories
        if self.product_data and 'categories' in self.product_data:
            categories = self.product_data['categories']
            if isinstance(categories, list) and len(categories) > 0:
                category = categories[-1]
                if isinstance(category, dict) and 'name' in category:
                    return category['name']

        return "Нет данных"

    def _get_attributes_dict(self) -> Dict[str, str]:
        attributes_dict = {}

        if self.product_data and 'featureGroups' in self.product_data:
            for group in self.product_data['featureGroups']:
                if 'features' in group:
                    for feature in group['features']:
                        try:
                            name = feature.get('name', '')
                            feature_values = feature.get('featureValues', [])

                            if name and feature_values:
                                values = []
                                for value_obj in feature_values:
                                    if isinstance(value_obj, dict) and 'value' in value_obj:
                                        values.append(value_obj['value'])
                                    elif isinstance(value_obj, str):
                                        values.append(value_obj)

                                if values:
                                    attributes_dict[name] = ', '.join(values)

                        except Exception:
                            continue

        return attributes_dict

    def _get_attributes(self) -> List[Attribute]:
        attributes_dict = self._get_attributes_dict()
        return [Attribute(attr_name=key, attr_value=value)
                for key, value in attributes_dict.items()]

    def _get_price_info(self) -> List[PriceInfo]:
        if not self.price_data or 'payload' not in self.price_data:
            return [PriceInfo(qnt=1, discount=0, price=0)]

        product = self.price_data['payload'].get('product', {})

        if 'price' not in product:
            return [PriceInfo(qnt=1, discount=0, price=0)]

        price_data = product['price']

        # Основная цена
        main_price = float(price_data.get('value', 0))

        # Расчет скидки
        discount = 0
        if 'crossedPrice' in price_data and price_data['crossedPrice']:
            try:
                crossed_price = float(price_data['crossedPrice'])
                if crossed_price > main_price:
                    discount = round(((crossed_price - main_price) / crossed_price) * 100, 2)
            except (ValueError, TypeError):
                pass

        # Объемные цены
        volume_prices = product.get('volumePrices', [])
        if volume_prices:
            return self._parse_volume_prices(volume_prices, main_price, discount)

        return [PriceInfo(qnt=1, discount=discount, price=main_price)]

    def _parse_volume_prices(self, volume_prices: List[Dict], base_price: float, base_discount: float) -> List[
        PriceInfo]:
        """Парсинг объемных цен"""
        price_infos = []

        # Добавляем базовую цену
        price_infos.append(PriceInfo(qnt=1, discount=base_discount, price=base_price))

        for price_item in volume_prices:
            try:
                quantity = int(price_item.get('minQuantity', 1))  # ✅ Правильное поле
                price = float(price_item.get('value', 0))  # ✅ Правильное поле

                # Вычисляем скидку относительно базовой цены
                discount = 0
                if base_price > price:
                    discount = round(((base_price - price) / base_price) * 100, 2)

                price_infos.append(PriceInfo(qnt=quantity, discount=discount, price=price))

            except (ValueError, TypeError):
                continue

        return price_infos if price_infos else [PriceInfo(qnt=1, discount=0, price=0)]

    def _get_stock_info(self) -> str:
        if not self.price_data or 'payload' not in self.price_data:
            return "Нет данных"

        product = self.price_data['payload'].get('product', {})

        if 'stock' in product:
            stock_data = product['stock']

            # Берем stockLevel как есть
            if 'stockLevel' in stock_data:
                return str(stock_data['stockLevel'])

        return "Нет данных"

    def _get_unit_name(self) -> str:
        """Получает единицу измерения товара"""
        if self.price_data and 'payload' in self.price_data:
            product = self.price_data['payload'].get('product', {})
            return product.get('unitName', 'шт.')
        return 'шт.'

    def _create_supplier(self) -> Supplier:
        offer = SupplierOffer(
            price=self._get_price_info(),
            stock=self._get_stock_info(),
            delivery_time="Нет данных",
            package_info=self._get_unit_name(),
            purchase_url=self.product_url or f"https://www.komus.ru/p/{self.product_id}/"
        )

        return Supplier(supplier_offers=[offer])