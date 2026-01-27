import asyncio
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, TYPE_CHECKING

import yaml

from app.config.environment import get_environment_config
from app.logging import logger
from app.queue.constants import QueueItemType, USER_UPDATE_GAP_SECONDS

if TYPE_CHECKING:
    from app.queue.queue import AsyncQueue

USER_REFRESH_HOURS = 12


class UserStore:
    """File-based user data storage in data/users/<user_id>.yml"""
    
    def __init__(self):
        env_config = get_environment_config()
        self._users_path = f"{env_config.data_path}/users"
        self._ensure_directory()
    
    def _ensure_directory(self):
        if not os.path.exists(self._users_path):
            logger.info('Creating users directory')
            os.makedirs(self._users_path)
    
    def _get_user_file_path(self, user_id: str) -> str:
        safe_id = str(user_id).replace('/', '_').replace('\\', '_')
        return os.path.join(self._users_path, f"{safe_id}.yml")
    
    def get(self, user_id: str) -> Optional[Dict[str, Any]]:
        file_path = self._get_user_file_path(user_id)
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, 'r') as f:
                return yaml.load(f, Loader=yaml.CLoader)
        except (yaml.YAMLError, IOError) as e:
            logger.warning('Failed to read user file', extra={'user_id': user_id, 'error': str(e)})
            return None

    def get_user_timezone(self, user_id: str) -> Optional[str]:
        user_data = self.get(user_id)
        if user_data is None:
            return None
        timezone = user_data.get('timezone')
        if isinstance(timezone, str) and timezone:
            return timezone
        return None
    
    def save(self, user_id: str, messenger_type: str, user_data: Dict[str, Any]) -> None:
        file_path = self._get_user_file_path(user_id)
        data = {
            'updated_at': datetime.now(timezone.utc),
            'messenger_type': messenger_type,
            'username': user_data.get('username'),
            'email': user_data.get('email'),
            'first_name': user_data.get('first_name'),
            'last_name': user_data.get('last_name'),
            'timezone': user_data.get('timezone'),
        }
        try:
            with open(file_path, 'w') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
            logger.debug('Saved user data', extra={'user_id': user_id})
        except IOError as e:
            logger.error('Failed to save user file', extra={'user_id': user_id, 'error': str(e)})
    
    def is_expired(self, user_id: str) -> bool:
        user_data = self.get(user_id)
        if user_data is None:
            return True
        return self._is_data_expired(user_data)
    
    def _is_data_expired(self, user_data: Dict[str, Any]) -> bool:
        updated_at = user_data.get('updated_at')
        if not updated_at:
            return True
        try:
            if isinstance(updated_at, str):
                updated_at = datetime.fromisoformat(updated_at)
            expiry_time = updated_at + timedelta(hours=USER_REFRESH_HOURS)
            return datetime.now(timezone.utc) > expiry_time
        except (ValueError, TypeError):
            return True
    
    def get_next_refresh_time(self, user_id: str) -> datetime:
        user_data = self.get(user_id)
        return self._get_refresh_time_from_data(user_data)
    
    def _get_refresh_time_from_data(self, user_data: Optional[Dict[str, Any]]) -> datetime:
        if user_data is None:
            return datetime.now(timezone.utc)
        updated_at = user_data.get('updated_at')
        if not updated_at:
            return datetime.now(timezone.utc)
        try:
            if isinstance(updated_at, str):
                updated_at = datetime.fromisoformat(updated_at)
            return updated_at + timedelta(hours=USER_REFRESH_HOURS)
        except (ValueError, TypeError):
            return datetime.now(timezone.utc)
    
    def get_all_users_by_type(self, messenger_type: str) -> Dict[str, Dict[str, Any]]:
        """Get all stored users for a specific messenger type."""
        users = {}
        if not os.path.exists(self._users_path):
            return users
        
        for filename in os.listdir(self._users_path):
            if not filename.endswith('.yml'):
                continue
            user_id = filename[:-4]
            user_data = self.get(user_id)
            if user_data and user_data.get('messenger_type') == messenger_type:
                users[user_id] = user_data
        
        return users
    
    def get_all_stored_user_ids(self) -> List[str]:
        if not os.path.exists(self._users_path):
            return []
        user_ids = []
        for filename in os.listdir(self._users_path):
            if filename.endswith('.yml'):
                user_id = filename[:-4]
                user_ids.append(user_id)
        return user_ids


_user_store: Optional[UserStore] = None


def get_user_store() -> UserStore:
    global _user_store
    if _user_store is None:
        _user_store = UserStore()
    return _user_store


class UserUpdateScheduler:
    """Handles scheduling of user data refresh tasks."""
    
    def __init__(self, queue: 'AsyncQueue', messenger_type: str):
        self._queue = queue
        self._messenger_type = messenger_type
        self._gap_seconds = USER_UPDATE_GAP_SECONDS.get(messenger_type, 1.0)
        self._async_tasks: set = set()
    
    def schedule_update(self, user_id: str) -> None:
        """Schedule a user update with proper gap from last UPDATE_USER item."""
        async def schedule():
            latest = await self._queue.get_latest_item_by_type(QueueItemType.UPDATE_USER)
            now = datetime.now(timezone.utc)
            base_time = latest if latest and latest > now else now
            schedule_time = base_time + timedelta(seconds=self._gap_seconds)
            await self._queue.put(schedule_time, QueueItemType.UPDATE_USER, identifier=user_id)
            logger.debug('Scheduled user update', extra={'user_id': user_id})
        
        task = asyncio.create_task(schedule())
        self._async_tasks.add(task)
        task.add_done_callback(self._async_tasks.discard)
    
    async def schedule_all_stored(self) -> None:
        """Schedule updates for all stored users at startup.
        
        - Expired users: schedule with gaps between UPDATE_USER items
        - Non-expired users: schedule at updated_at + 12h
        """
        user_store = get_user_store()
        stored_users = user_store.get_all_users_by_type(self._messenger_type)
        if not stored_users:
            return
        
        now = datetime.now(timezone.utc)
        last_immediate_schedule = now
        
        for user_id, user_data in stored_users.items():
            if user_store._is_data_expired(user_data):
                schedule_time = last_immediate_schedule + timedelta(seconds=self._gap_seconds)
                last_immediate_schedule = schedule_time
            else:
                schedule_time = user_store._get_refresh_time_from_data(user_data)
            
            await self._queue.put(schedule_time, QueueItemType.UPDATE_USER, identifier=user_id)
        
        logger.info('Scheduled user refresh tasks', extra={'count': len(stored_users)})
