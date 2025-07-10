from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    base_url: str = Field(default="https://www.komus.ru/")

    mongo_url: str = Field(default="mongodb://localhost:27017/")
    db_name: str = Field(default="komus_parser")
    collection_name: str = Field(default="products")

    log_level: str = Field(default="INFO")
    log_format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()