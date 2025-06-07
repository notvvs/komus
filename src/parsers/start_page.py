from bs4 import BeautifulSoup

from src.core.settings import settings
from src.parsers.base_parser import BaseParser


class StartPageParser(BaseParser):
    async def parse_page(self, html: str):
        categories = []

        soup = BeautifulSoup(html, 'html.parser')

        category_blocks = soup.find_all('div', class_="categories__item")

        for category_block in category_blocks:
            sub_category = category_block.find_all('li', class_="categories__subcategory")
            for li in sub_category:
                link = li.find('a', class_="categories__link")
                if link:
                    href = link["href"]
                    categories.append(settings.base_url + href)
        return categories


