from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    base_url: str = 'https://www.komus.ru/'

settings = Settings()