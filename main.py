import asyncio

from src.parsers.start_page import start_page_parser
from src.scrapers.start_page import start_page_scraper


async def test(url):
    html = await start_page_scraper.scrape_page(url)
    test = await start_page_parser.parse_page(html)
    return test

print(asyncio.run(test('https://www.komus.ru/katalog/c/0/?from=menu-v1-vse_kategorii')))