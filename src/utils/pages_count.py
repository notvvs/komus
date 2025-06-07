import math

from bs4 import BeautifulSoup


async def pages_count(soup: BeautifulSoup) -> int:

    items_cnt = soup.find('span', class_="catalog__header-sup").get_text(strip=True)
    pages_cnt = math.ceil(int(items_cnt) / 30)

    return pages_cnt