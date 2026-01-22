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
    """User registry for BaseUser objects."""
    
    def __init__(self):
        self._users: Dict[str, BaseUser] = {}
    
    def add_user(self, name: str, user: BaseUser) -> None:
        self._users[name] = user
    
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
