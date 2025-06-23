import asyncio
import re
import logging
from typing import List, Optional, Dict, Any
import json

from src.core.settings import settings
from src.parsers.base_parser import BaseParser
from src.schemas.product import Product, Attribute, PriceInfo, SupplierOffer, Supplier
from src.utils.http_requests import make_request, refresh_session_on_503

logger = logging.getLogger(__name__)


class KomusParser(BaseParser):
    """Парсер товаров Komus через API"""

    def __init__(self, product_id: str = None, product_url: str = None):
        self.product_id = product_id
        self.product_url = product_url
        self.api_data = None
        self._default_return_type = 'product'

        # Извлекаем ID из URL если не передан напрямую
        if not self.product_id and self.product_url:
            self.product_id = self._extract_product_id_from_url(self.product_url)

    def _extract_product_id_from_url(self, url: str) -> str:
        """Извлечение ID товара из URL"""
        match = re.search(r'/p/(\d+)/', url)
        return match.group(1) if match else ""

    async def parse_page(self, product_id: str = None, product_url: str = None) -> Product:
        """Основной метод парсинга товара через API"""
        if product_id:
            self.product_id = product_id
        elif product_url:
            self.product_url = product_url
            self.product_id = self._extract_product_id_from_url(product_url)

        if not self.product_id:
            logger.error("Product ID not found")
            return self._create_error_product("Не удалось извлечь ID товара")

        logger.info(f"Parsing product via API: {self.product_id}")

        try:
            # Получаем данные через API
            self.api_data = await self._get_product_api_data()

            if not self.api_data:
                logger.error(f"Failed to get API data for product {self.product_id}")
                return self._create_error_product("Не удалось получить данные через API")

            # Создаем продукт из API данных
            product = await self._create_product_from_api()

            logger.info(f"Successfully parsed product: {product.title[:50]}...")
            return product

        except Exception as e:
            logger.error(f"Error parsing product {self.product_id}: {e}")
            return self._create_error_product(f"Ошибка парсинга: {str(e)}")

    async def _get_product_api_data(self) -> Optional[Dict[str, Any]]:
        """Получение данных товара через API"""
        try:
            # API endpoint для товара
            api_url = f"https://www.komus.ru/api/product/{self.product_id}"

            # Параметры API запроса
            params = {
                'fields': 'featureGroups,productSet,trademark,name,description,code,price,stock,images,categories'
            }

            # Заголовки для API запроса
            api_headers = {
                'accept': 'application/json',
                'accept-language': 'ru,en;q=0.9',
                'priority': 'u=1, i',
                'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "YaBrowser";v="25.4", "Yowser";v="2.5"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"macOS"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-origin',
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 YaBrowser/25.4.0.0 Safari/537.36',
                'x-requested-with': 'XMLHttpRequest'
            }

            # Если есть referer (оригинальная страница товара), добавляем
            if self.product_url:
                api_headers['referer'] = self.product_url

            # Используем session manager - сессия создается только при необходимости
            response = await make_request(
                url=api_url,
                headers=api_headers,
                method="GET",
                params=params,
                max_retries=3
            )

            if response.status_code == 200:
                try:
                    return response.json()
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode JSON response: {e}")
                    return None
            else:
                logger.error(f"API request failed with status {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error getting API data for product {self.product_id}: {e}")
            return None

    async def _create_product_from_api(self) -> Product:
        """Создание объекта Product из API данных"""
        return Product(
            title=await self._get_title_from_api(),
            description=await self._get_description_from_api(),
            article=self.product_id,
            brand=await self._get_brand_from_api(),
            country_of_origin=await self._get_country_from_api(),
            warranty_months=await self._get_warranty_from_api(),
            category=await self._get_category_from_api(),
            attributes=await self._get_attributes_from_api(),
            suppliers=[await self._create_supplier_from_api()]
        )

    def _create_error_product(self, error_msg: str) -> Product:
        """Создание продукта с ошибкой"""
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

    async def _get_title_from_api(self) -> str:
        """Извлечение названия товара из API"""
        try:
            # Пытаемся получить название из разных возможных полей
            if 'name' in self.api_data:
                return self.api_data['name']
            elif 'title' in self.api_data:
                return self.api_data['title']
            elif 'productName' in self.api_data:
                return self.api_data['productName']
        except Exception as e:
            logger.error(f"Error getting title from API: {e}")

        return "Нет данных"

    async def _get_description_from_api(self) -> str:
        """Извлечение описания товара из API"""
        try:
            if 'description' in self.api_data:
                return self.api_data['description']
            elif 'shortDescription' in self.api_data:
                return self.api_data['shortDescription']
        except Exception as e:
            logger.error(f"Error getting description from API: {e}")

        return "Нет данных"

    async def _get_brand_from_api(self) -> str:
        """Извлечение бренда из API"""
        try:
            # Сначала пытаемся получить из trademark
            if 'trademark' in self.api_data and self.api_data['trademark']:
                trademark = self.api_data['trademark']
                if 'name' in trademark:
                    return trademark['name']

            # Если не нашли в trademark, ищем в характеристиках
            brand_keys = ['Торговая марка', 'Бренд', 'Производитель', 'Марка']
            attributes_dict = await self._get_attributes_dict_from_api()

            for key in brand_keys:
                if key in attributes_dict:
                    return attributes_dict[key]

        except Exception as e:
            logger.error(f"Error getting brand from API: {e}")

        return "Нет данных"

    async def _get_country_from_api(self) -> str:
        """Извлечение страны происхождения из API"""
        try:
            country_keys = ['Страна происхождения', 'Страна-производитель', 'Страна изготовления']
            attributes_dict = await self._get_attributes_dict_from_api()

            for key in country_keys:
                if key in attributes_dict:
                    return attributes_dict[key]

        except Exception as e:
            logger.error(f"Error getting country from API: {e}")

        return "Нет данных"

    async def _get_warranty_from_api(self) -> str:
        """Извлечение гарантийного срока из API"""
        try:
            warranty_keys = ['Гарантийный срок', 'Гарантия', 'Срок гарантии']
            attributes_dict = await self._get_attributes_dict_from_api()

            for key in warranty_keys:
                if key in attributes_dict:
                    value = attributes_dict[key]
                    # Если есть единица измерения, добавляем её
                    if key == 'Гарантийный срок' and value.isdigit():
                        return f"{value} мес"
                    return value

        except Exception as e:
            logger.error(f"Error getting warranty from API: {e}")

        return "Нет данных"

    async def _get_category_from_api(self) -> str:
        """Извлечение категории из API"""
        try:
            # Пытаемся получить категорию из разных возможных полей
            if 'categories' in self.api_data and self.api_data['categories']:
                categories = self.api_data['categories']
                if isinstance(categories, list) and len(categories) > 0:
                    # Берем последнюю категорию (наиболее специфичную)
                    category = categories[-1]
                    if isinstance(category, dict) and 'name' in category:
                        return category['name']
                    elif isinstance(category, str):
                        return category

            # Можно также попытаться извлечь из URL если есть
            if self.product_url:
                # Пытаемся извлечь категорию из URL
                url_parts = self.product_url.split('/')
                for i, part in enumerate(url_parts):
                    if part == 'katalog' and i + 2 < len(url_parts):
                        return url_parts[i + 2].replace('-', ' ').title()

        except Exception as e:
            logger.error(f"Error getting category from API: {e}")

        return "Нет данных"

    async def _get_attributes_dict_from_api(self) -> Dict[str, str]:
        """Извлечение всех характеристик в виде словаря из API"""
        try:
            attributes_dict = {}

            if 'featureGroups' in self.api_data:
                for group in self.api_data['featureGroups']:
                    if 'features' in group:
                        for feature in group['features']:
                            try:
                                name = feature.get('name', '')
                                feature_values = feature.get('featureValues', [])

                                if name and feature_values:
                                    # Собираем все значения характеристики
                                    values = []
                                    for value_obj in feature_values:
                                        if isinstance(value_obj, dict) and 'value' in value_obj:
                                            values.append(value_obj['value'])
                                        elif isinstance(value_obj, str):
                                            values.append(value_obj)

                                    if values:
                                        # Если несколько значений, соединяем их
                                        combined_value = ', '.join(values)
                                        attributes_dict[name] = combined_value

                            except Exception as e:
                                logger.debug(f"Error parsing feature: {e}")
                                continue

            logger.info(f"Extracted {len(attributes_dict)} attributes from API")
            return attributes_dict

        except Exception as e:
            logger.error(f"Error getting attributes from API: {e}")
            return {}

    async def _get_attributes_from_api(self) -> List[Attribute]:
        """Преобразование характеристик в список объектов из API"""
        attributes_dict = await self._get_attributes_dict_from_api()
        return [Attribute(attr_name=key, attr_value=value) for key, value in attributes_dict.items()]

    async def _get_price_info_from_api(self) -> List[PriceInfo]:
        """Извлечение информации о ценах из API"""
        try:
            # Если есть информация о ценах в API данных
            if 'price' in self.api_data:
                price_data = self.api_data['price']

                # Может быть простая цена
                if isinstance(price_data, (int, float)):
                    return [PriceInfo(qnt=1, discount=0, price=float(price_data))]

                # Или сложная структура с объемными скидками
                elif isinstance(price_data, dict):
                    if 'value' in price_data:
                        main_price = float(price_data['value'])

                        # Проверяем наличие объемных цен
                        if 'volumePrices' in price_data:
                            return await self._parse_volume_prices_from_api(price_data['volumePrices'])
                        else:
                            # Проверяем наличие скидки
                            discount = 0
                            if 'oldPrice' in price_data and price_data['oldPrice']:
                                old_price = float(price_data['oldPrice'])
                                if old_price > main_price:
                                    discount = round(((old_price - main_price) / old_price) * 100, 2)

                            return [PriceInfo(qnt=1, discount=discount, price=main_price)]

            return [PriceInfo(qnt=1, discount=0, price=0)]

        except Exception as e:
            logger.error(f"Error getting price from API: {e}")
            return [PriceInfo(qnt=1, discount=0, price=0)]

    async def _parse_volume_prices_from_api(self, volume_prices: List[Dict]) -> List[PriceInfo]:
        """Парсинг объемных цен из API"""
        try:
            price_infos = []

            for price_item in volume_prices:
                try:
                    quantity = int(price_item.get('quantity', 1))
                    price = float(price_item.get('price', 0))

                    # Вычисляем скидку относительно первой цены
                    discount = 0
                    if price_infos:
                        base_price = price_infos[0].price
                        if base_price > price:
                            discount = round(((base_price - price) / base_price) * 100, 2)

                    price_infos.append(PriceInfo(qnt=quantity, discount=discount, price=price))

                except (ValueError, TypeError) as e:
                    logger.debug(f"Error parsing volume price item: {e}")
                    continue

            return price_infos if price_infos else [PriceInfo(qnt=1, discount=0, price=0)]

        except Exception as e:
            logger.error(f"Error parsing volume prices from API: {e}")
            return [PriceInfo(qnt=1, discount=0, price=0)]

    async def _get_stock_info_from_api(self) -> str:
        """Извлечение информации о наличии из API"""
        try:
            if 'stock' in self.api_data:
                stock_data = self.api_data['stock']

                if isinstance(stock_data, dict):
                    if 'level' in stock_data:
                        return str(stock_data['level'])
                    elif 'status' in stock_data:
                        return stock_data['status']
                elif isinstance(stock_data, str):
                    return stock_data

        except Exception as e:
            logger.error(f"Error getting stock from API: {e}")

        return "Нет данных"

    async def _create_supplier_from_api(self) -> Supplier:
        """Создание объекта поставщика из API данных"""
        offer = SupplierOffer(
            price=await self._get_price_info_from_api(),
            stock=await self._get_stock_info_from_api(),
            delivery_time="Нет данных",  # Возможно есть в API, нужно проверить
            package_info="Нет данных",  # Возможно есть в API, нужно проверить
            purchase_url=self.product_url or f"https://www.komus.ru/p/{self.product_id}/"
        )

        return Supplier(supplier_offers=[offer])