from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения с поддержкой .env файлов"""

    base_url: str = Field(default="https://www.komus.ru/")

    mongo_url: str = Field(default="mongodb://localhost:27017/")
    db_name: str = Field(default="komus_parser")
    collection_name: str = Field(default="products")

    default_categories_limit: int = Field(default=0)
    default_products_limit: int = Field(default=0)

    page_timeout: int = Field(default=15000)
    navigation_timeout: int = Field(default=15000)

    page_load_delay: float = Field(default=2.0)
    scroll_delay: float = Field(default=0.3)
    product_load_delay: float = Field(default=3.0)

    headless_mode: bool = Field(default=True)
    user_agent: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    viewport_width: int = Field(default=1920)
    viewport_height: int = Field(default=1080)

    log_level: str = Field(default="INFO")
    log_format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    max_retries: int = Field(default=3)
    retry_delay: float = Field(default=5.0)
    playwright_debug: bool = Field(default=False)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()