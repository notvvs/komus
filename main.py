import asyncio
import logging
from src.core.settings import settings
from src.services.parser_service import KomusParserService


def setup_logging():
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(level=log_level, format=settings.log_format)


async def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("🚀 Запуск парсера Komus")

    async with KomusParserService() as service:
        await service.run_parsing()


if __name__ == "__main__":
    asyncio.run(main())