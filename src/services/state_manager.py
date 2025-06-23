import json
import os
from datetime import datetime
from typing import Optional, Dict, List
import logging

from src.repository.mongo_client import mongo_client

logger = logging.getLogger(__name__)


class ParserStateManager:
    """Управление состоянием парсера для возможности возобновления"""

    def __init__(self, use_mongodb: bool = True):
        self.use_mongodb = use_mongodb
        self.state_file = "parser_state.json"
        self.collection_name = "parser_state"
        self.state_id = "komus_parser_state"

    async def save_state(self, state: Dict):
        """Сохраняет текущее состояние парсера"""
        state['last_updated'] = datetime.now().isoformat()

        if self.use_mongodb:
            await self._save_to_mongodb(state)
        else:
            self._save_to_file(state)

    async def load_state(self) -> Optional[Dict]:
        """Загружает сохраненное состояние"""
        if self.use_mongodb:
            return await self._load_from_mongodb()
        else:
            return self._load_from_file()

    async def clear_state(self):
        """Очищает сохраненное состояние"""
        if self.use_mongodb:
            await self._clear_mongodb_state()
        else:
            self._clear_file_state()

    # MongoDB методы
    async def _save_to_mongodb(self, state: Dict):
        """Сохраняет состояние в MongoDB"""
        try:
            collection = mongo_client.get_collection(self.collection_name)
            await collection.replace_one(
                {"_id": self.state_id},
                {"_id": self.state_id, **state},
                upsert=True
            )
            logger.info("State saved to MongoDB")
        except Exception as e:
            logger.error(f"MongoDB state save error: {e}")
            # Fallback to file
            self._save_to_file(state)

    async def _load_from_mongodb(self) -> Optional[Dict]:
        """Загружает состояние из MongoDB"""
        try:
            collection = mongo_client.get_collection(self.collection_name)
            state = await collection.find_one({"_id": self.state_id})
            if state:
                state.pop('_id', None)
                return state
        except Exception as e:
            logger.error(f"MongoDB state load error: {e}")
        return None

    async def _clear_mongodb_state(self):
        """Удаляет состояние из MongoDB"""
        try:
            collection = mongo_client.get_collection(self.collection_name)
            await collection.delete_one({"_id": self.state_id})
        except Exception as e:
            logger.error(f"MongoDB state clear error: {e}")

    # Файловые методы
    def _save_to_file(self, state: Dict):
        """Сохраняет состояние в файл"""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            logger.info(f"State saved to {self.state_file}")
        except Exception as e:
            logger.error(f"File state save error: {e}")

    def _load_from_file(self) -> Optional[Dict]:
        """Загружает состояние из файла"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"File state load error: {e}")
        return None

    def _clear_file_state(self):
        """Удаляет файл состояния"""
        if os.path.exists(self.state_file):
            try:
                os.remove(self.state_file)
            except Exception as e:
                logger.error(f"File state delete error: {e}")


class ParserState:
    """Класс для хранения состояния парсера"""

    def __init__(self):
        self.visited_urls: List[str] = []
        self.processed_categories: List[str] = []
        self.current_main_category_index: int = 0
        self.total_categories_processed: int = 0
        self.total_products_processed: int = 0
        self.start_time: str = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        """Преобразует состояние в словарь"""
        return {
            'visited_urls': self.visited_urls,
            'processed_categories': self.processed_categories,
            'current_main_category_index': self.current_main_category_index,
            'total_categories_processed': self.total_categories_processed,
            'total_products_processed': self.total_products_processed,
            'start_time': self.start_time
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ParserState':
        """Создает объект состояния из словаря"""
        state = cls()
        state.visited_urls = data.get('visited_urls', [])
        state.processed_categories = data.get('processed_categories', [])
        state.current_main_category_index = data.get('current_main_category_index', 0)
        state.total_categories_processed = data.get('total_categories_processed', 0)
        state.total_products_processed = data.get('total_products_processed', 0)
        state.start_time = data.get('start_time', datetime.now().isoformat())
        return state