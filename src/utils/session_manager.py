import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
import threading

from src.utils.http_requests import refresh_session_on_503

logger = logging.getLogger(__name__)


class SessionManager:
    """Глобальный менеджер сессий для переиспользования cookies и headers"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SessionManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.session_data: Optional[Dict] = None
            self.session_created_at: Optional[datetime] = None
            self.session_refresh_in_progress = False
            self.session_lock = asyncio.Lock()
            self.max_session_age = timedelta(hours=2)  # Максимальный возраст сессии
            self.initialized = True

    async def get_session(self) -> Dict:
        """Получение актуальной сессии"""
        async with self.session_lock:
            # Если сессии нет или она устарела, создаем новую
            if self._should_refresh_session():
                logger.info("🔄 Создание новой сессии...")
                await self._refresh_session()

            return self.session_data

    async def refresh_session_on_error(self) -> Dict:
        """Принудительное обновление сессии при ошибке"""
        async with self.session_lock:
            if self.session_refresh_in_progress:
                logger.info("⏳ Ожидание завершения обновления сессии...")
                # Ждем пока другой поток обновит сессию
                while self.session_refresh_in_progress:
                    await asyncio.sleep(0.1)
                return self.session_data

            logger.warning("🔄 Принудительное обновление сессии из-за ошибки...")
            await self._refresh_session()
            return self.session_data

    def _should_refresh_session(self) -> bool:
        """Проверка необходимости обновления сессии"""
        if self.session_data is None:
            return True

        if self.session_created_at is None:
            return True

        # Проверяем возраст сессии
        if datetime.now() - self.session_created_at > self.max_session_age:
            logger.info("⏰ Сессия устарела, требуется обновление")
            return True

        return False

    async def _refresh_session(self):
        """Внутренний метод обновления сессии"""
        try:
            self.session_refresh_in_progress = True

            # Получаем новую сессию
            new_session_data = await refresh_session_on_503()

            if new_session_data:
                self.session_data = new_session_data
                self.session_created_at = datetime.now()
                logger.info("✅ Сессия успешно обновлена")
            else:
                logger.error("❌ Не удалось обновить сессию")

        except Exception as e:
            logger.error(f"❌ Ошибка обновления сессии: {e}")
        finally:
            self.session_refresh_in_progress = False

    def get_session_info(self) -> Dict:
        """Информация о текущей сессии"""
        if not self.session_data:
            return {"status": "no_session"}

        age = datetime.now() - self.session_created_at if self.session_created_at else None

        return {
            "status": "active",
            "created_at": self.session_created_at.isoformat() if self.session_created_at else None,
            "age_minutes": age.total_seconds() / 60 if age else None,
            "cookies_count": len(self.session_data.get('cookies', {})),
            "headers_count": len(self.session_data.get('headers', {}))
        }


# Глобальный экземпляр менеджера сессий
session_manager = SessionManager()