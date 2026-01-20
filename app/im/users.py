import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import Union, Optional, Dict, TYPE_CHECKING

from app.logging import logger
from app.queue.constants import QueueItemType, USER_UPDATE_GAP_SECONDS

if TYPE_CHECKING:
    from app.queue.queue import AsyncQueue


class BaseUser(ABC):
    """Base class for all messenger users."""
    
    def __init__(self, name: str, id_: Union[int, str, None] = None, exists: bool = False):
        self.name = name
        self.id = id_
        self.exists = exists
        self.defined = True
    
    def __repr__(self):
        return self.name
    
    @abstractmethod
    def get_notification_identifier(self) -> Union[int, str, None]:
        """Return the platform-specific identifier used for mentions/notifications."""
        pass


class UndefinedUser(BaseUser):
    def __init__(self, name: str):
        super().__init__(name, None, False)
        self.defined = False
    
    def get_notification_identifier(self):
        return None


class UserManager:
    """User registry with queue integration for update scheduling."""
    
    def __init__(self):
        self._users: Dict[str, BaseUser] = {}
        self._queue: Optional['AsyncQueue'] = None
        self._messenger_type: Optional[str] = None
    
    def configure_queue(self, queue: 'AsyncQueue', messenger_type: str) -> None:
        """Configure queue for user update scheduling."""
        self._queue = queue
        self._messenger_type = messenger_type
    
    def add_user(self, name: str, user: BaseUser) -> None:
        self._users[name] = user
    
    def schedule_user_update(self, user_id: str) -> None:
        """Schedule a user update with proper gap from last UPDATE_USER item."""
        if self._queue is None:
            return
        
        async def schedule():
            gap_seconds = USER_UPDATE_GAP_SECONDS.get(self._messenger_type, 1.0)
            latest = await self._queue.get_latest_item_by_type(QueueItemType.UPDATE_USER)
            now = datetime.now(timezone.utc)
            base_time = latest if latest and latest > now else now
            schedule_time = base_time + timedelta(seconds=gap_seconds)
            await self._queue.put(schedule_time, QueueItemType.UPDATE_USER, identifier=user_id)
            logger.debug(f'Scheduled user update for {user_id}')
        
        asyncio.create_task(schedule())
    
    def get_user(self, name: str) -> BaseUser:
        return self._users.get(name, UndefinedUser(name))
    
    def get(self, name: str, default=None) -> Optional[BaseUser]:
        return self._users.get(name, default)
    
    def get_all_users(self) -> Dict[str, BaseUser]:
        return self._users.copy()
    
    def __getitem__(self, name: str) -> BaseUser:
        return self.get_user(name)
    
    def __contains__(self, name: str) -> bool:
        return name in self._users
    
    def get_user_by_id(self, user_id: Union[int, str]) -> Optional[BaseUser]:
        for user in self._users.values():
            if user.id == user_id:
                return user
        return None
