from abc import abstractmethod, ABC

from src.schemas.product import Product


class BaseParser(ABC):
    @abstractmethod
    async def parse_page(self, html: str):
        pass

class BaseParserBrowser(ABC):
    """Базовый абстрактный класс для парсеров"""

    @abstractmethod
    async def parse_page(self, page) -> Product:
        """Парсинг страницы товара"""
        pass