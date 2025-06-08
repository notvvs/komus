import logging
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)


class MongoClient:
    def __init__(self):
        self.client = None
        self.database = None

    async def connect(self):
        self.client = AsyncIOMotorClient("mongodb://localhost:27017")
        await self.client.admin.command('ping')
        self.database = self.client["komus_parser"]
        logger.info("✅ MongoDB подключен")

    async def disconnect(self):
        if self.client:
            self.client.close()

    def get_collection(self, name: str):
        return self.database[name]


mongo_client = MongoClient()