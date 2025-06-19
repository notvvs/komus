import logging
from motor.motor_asyncio import AsyncIOMotorClient
from src.core.settings import settings

logger = logging.getLogger(__name__)


class MongoClient:
    def __init__(self):
        self.client = None
        self.database = None

    async def connect(self):
        self.client = AsyncIOMotorClient(settings.mongo_url)
        await self.client.admin.command('ping')
        self.database = self.client[settings.db_name]
        logger.info(f"✅ MongoDB подключен: {settings.db_name}")

    async def disconnect(self):
        if self.client:
            self.client.close()

    def get_collection(self, name: str):
        return self.database[name]


mongo_client = MongoClient()