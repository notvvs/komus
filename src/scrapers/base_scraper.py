from abc import abstractmethod, ABC


class BaseScraper(ABC):
    @abstractmethod
    async def scrape_page(self, page, url: str):
        """Скрапинг страницы через Playwright"""
        pass