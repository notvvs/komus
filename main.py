import asyncio
import logging
import sys
from src.core.settings import settings
from src.services.parser_service import KomusParserService


def setup_logging():
    """Настройка логирования из .env"""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format=settings.log_format
    )


async def main():
    """Главная функция запуска парсера"""
    setup_logging()

    logger = logging.getLogger(__name__)

    # Проверяем аргументы командной строки
    resume = True  # По умолчанию пытаемся возобновить
    if len(sys.argv) > 1 and sys.argv[1] == '--new':
        resume = False
        logger.info("🆕 Запуск нового парсинга (--new)")

    logger.info("🚀 Запуск парсера Komus")
    logger.info(f"🔧 Лимит категорий: {settings.default_categories_limit or 'без лимитов'}")
    logger.info(f"🔧 Лимит товаров: {settings.default_products_limit or 'без лимитов'}")
    logger.info(f"🔧 Headless режим: {settings.headless_mode}")
    logger.info(f"🔧 Возобновление: {'Да' if resume else 'Нет'}")

    try:
        async with KomusParserService() as service:
            await service.run_parsing(
                limit_categories=settings.default_categories_limit or None,
                limit_products=settings.default_products_limit or None,
                resume=resume
            )
    except KeyboardInterrupt:
        logger.info("\n👋 Парсинг остановлен. До свидания!")
    except Exception as e:
        logger.error(f"\n💥 Неожиданная ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())