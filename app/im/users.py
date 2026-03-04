from abc import ABC, abstractmethod
from typing import Union, Optional, Dict


class BaseUser(ABC):
    """Base class for all messenger users."""
    
    def __init__(self, name: str, id_: Union[int, str, None] = None, exists: bool = False, full_name: str = None, username: str = None, timezone: Optional[str] = None):
        self.name = name
        self.id = id_
        self.exists = exists
        self.defined = True
        self.full_name = full_name
        self.username = username
        self.timezone = timezone

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
    
    def add_config_name(self, config_name: str, user_id: str) -> None:
        """Add a config name mapping for an existing user."""
        self._config_names[config_name] = user_id
    
    def add_user(self, user_id: str, user: BaseUser, config_name: str = None) -> None:
        """Add a user by user_id, optionally with a config name mapping."""
        self._users[user_id] = user
        if config_name:
            self._config_names[config_name] = user_id

    def get(self, name: str, default=None) -> Optional[BaseUser]:
        """Get user by config name or user_id. Returns default if not found."""
        user = self._resolve_user(name)
        if isinstance(user, UndefinedUser):
            return default
        return user
    
    def get_user_by_id(self, user_id: Union[int, str]) -> Optional[BaseUser]:
        """Get user by their messenger ID."""
        str_id = str(user_id)
        if str_id in self._users:
            return self._users[str_id]
        return None

    def get_user_timezone(self, user_id: str) -> Optional[str]:
        user = self.get_user_by_id(user_id)
        if user and user.timezone:
            return user.timezone
        return None
    
    ### private methods ###
    def _resolve_user(self, name: str) -> BaseUser:
        """Resolve a name to a user, checking config names first, then user_ids."""
        if name in self._config_names:
            user_id = self._config_names[name]
            user = self._users.get(user_id)
            return user if user else UndefinedUser(name)
        return UndefinedUser(name)
