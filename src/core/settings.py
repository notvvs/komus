from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    base_url: str = 'https://www.komus.ru/'
    db_name: str = 'test'
    mongo_url: str = 'mongodb://localhost:27017/'

settings = Settings()