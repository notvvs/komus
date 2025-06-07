from abc import abstractmethod, ABC


class BaseParser(ABC):
    @abstractmethod
    async def parse_page(self, html: str):
        pass