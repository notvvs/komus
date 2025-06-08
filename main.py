import asyncio
import logging
from src.services.parser_service import KomusParserService


async def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

    async with KomusParserService() as service:
        await service.run_parsing(
            limit_categories=1,
            limit_products=None
        )


if __name__ == "__main__":
    asyncio.run(main())