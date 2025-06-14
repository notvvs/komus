import asyncio
import logging
from src.services.parser_service import KomusParserService


async def main():
    """Главная функция запуска парсера"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    async with KomusParserService() as service:
        await service.run_parsing(
            limit_categories=2,  # Ограничение категорий для тестирования
            limit_products=5     # Ограничение товаров для тестирования
        )


if __name__ == "__main__":
    asyncio.run(main())