import json
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar, Optional, Set 

from app.config.config import get_config
from app.logging import logger


class UserCache:
    """Manages cache for users"""
    
    CACHE_FIELDS: ClassVar[list[str]] = [
        'update_at',
        'username',
        'email',
        'first_name',
        'last_name',
        'timezone'
    ]
    
    def __init__(self):
        config = get_config()
        self.CACHE_DIR = Path(config.data_path) / "cache" / "users"
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_path(self, user_id: str) -> Path:
        """Get cache file path for user_id"""
        return self.CACHE_DIR / f"{user_id}.json"
    
    def get(self, user_id: str) -> Optional[dict]:
        """
        Get cached user data
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with user data or None if not cached
        """
        cache_path = self._get_cache_path(user_id)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to read cache for user {user_id}: {e}")
            return None
    
    def set(self, user_id: str, user_data: dict) -> None:
        """
        Save user data to cache
        
        Args:
            user_id: User ID
            user_data: Dictionary with user data from get_user_details()
        """
        cache_path = self._get_cache_path(user_id)

        cache_data = {
            'update_at': datetime.now(timezone.utc).isoformat(),
            'username': user_data.get('username') or '',
            'email': user_data.get('email') or '',
            'first_name': user_data.get('first_name') or '',
            'last_name': user_data.get('last_name') or '',
            'timezone': user_data.get('timezone') or '',
        }
        
        for field in self.CACHE_FIELDS:
            if field not in cache_data:
                cache_data[field] = ''
        
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            logger.debug(f"Cached user data for {user_id}")
        except IOError as e:
            logger.error(f"Failed to write cache for user {user_id}: {e}")
    
    def get_full_name(self, user_id: str) -> Optional[str]:
        """
        Get full name from cache
        
        Args:
            user_id: User ID
            
        Returns:
            Full name string or None if not cached
        """
        cached = self.get(user_id)
        if not cached:
            return None
        
        first_name = cached.get('first_name') or ''
        last_name = cached.get('last_name') or ''
        full_name = f"{first_name} {last_name}".strip()
        return full_name
    
    def get_all_cached_user_ids(self) -> Set[str]:
        """
        Get all user IDs that have cached data
        
        Returns:
            Set of user IDs
        """
        if not self.CACHE_DIR.exists():
            return set()
        
        user_ids = set()
        for cache_file in self.CACHE_DIR.glob("*.json"):
            user_id = cache_file.stem
            user_ids.add(user_id)
        
        return user_ids
