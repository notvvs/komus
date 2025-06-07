from abc import abstractmethod, ABC


class BaseScraper(ABC):

    @abstractmethod
    async def scrape_page(self, url: str) -> str:
        pass