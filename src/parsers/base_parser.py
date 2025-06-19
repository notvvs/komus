from abc import abstractmethod, ABC
from typing import Union, List, Any
from src.schemas.product import Product


class BaseParser(ABC):
    """Единый базовый класс для всех парсеров"""

    @abstractmethod
    async def parse_page(self, page, *args, **kwargs) -> Union[Product, List[str]]:
        """Парсинг страницы - возвращает Product для товара или List[str] для категорий/ссылок"""
        pass