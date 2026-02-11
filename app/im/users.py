from abc import ABC, abstractmethod
from typing import Union, Optional, Dict


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
    """User registry for BaseUser objects.
    
    Users are stored by user_id as the primary key.
    Config names are mapped to user_ids for lookup compatibility.
    """
    
    def __init__(self):
        self._users: Dict[str, BaseUser] = {}  # user_id -> BaseUser
        self._config_names: Dict[str, str] = {}  # config_name -> user_id
    
    def add_user(self, user_id: str, user: BaseUser, config_name: str = None) -> None:
        """Add a user by user_id, optionally with a config name mapping."""
        self._users[user_id] = user
        if config_name:
            self._config_names[config_name] = user_id
    
    def add_config_name(self, config_name: str, user_id: str) -> None:
        """Add a config name mapping for an existing user."""
        self._config_names[config_name] = user_id
    
    def get_user(self, name: str) -> BaseUser:
        """Get user by config name or user_id. Returns UndefinedUser if not found."""
        user = self._resolve_user(name)
        return user if user else UndefinedUser(name)
    
    def get(self, name: str, default=None) -> Optional[BaseUser]:
        """Get user by config name or user_id. Returns default if not found."""
        user = self._resolve_user(name)
        return user if user else default
    
    def _resolve_user(self, name: str) -> Optional[BaseUser]:
        """Resolve a name to a user, checking config names first, then user_ids."""
        if name in self._config_names:
            user_id = self._config_names[name]
            return self._users.get(user_id)
        return self._users.get(name)
    
    def __getitem__(self, name: str) -> BaseUser:
        return self.get_user(name)
    
    def get_user_by_id(self, user_id: Union[int, str]) -> Optional[BaseUser]:
        """Get user by their messenger ID."""
        str_id = str(user_id)
        if str_id in self._users:
            return self._users[str_id]
        return None
