from abc import ABC, abstractmethod


class BaseUser(ABC):
    """Base class for all messenger users."""
    
    def __init__(self, name: str, id_: int | str | None = None, exists: bool = False, full_name: str | None = None, username: str | None = None, timezone: str | None = None, roles: list[str] | None = None):
        self.name = name
        self.id = id_
        self.exists = exists
        self.defined = True
        self.full_name = full_name
        self.username = username
        self.timezone = timezone
        self.roles = roles or []

    def __repr__(self):
        return self.name
    
    @abstractmethod
    def get_notification_identifier(self) -> int | str | None:
        """Return the platform-specific identifier used for mentions/notifications."""

    @abstractmethod
    def serialize(self) -> dict:
        """Return the messenger-specific API payload for this user."""


class UndefinedUser(BaseUser):
    def __init__(self, name: str):
        super().__init__(name, None, False)
        self.defined = False
    
    def get_notification_identifier(self):
        return None

    def serialize(self) -> dict:
        return {
            'exists': self.exists,
            'full_name': None,
            'id': None,
            'roles': list(self.roles),
            'username': None,
        }


class UserManager:
    def __init__(self):
        self._users: dict[str, BaseUser] = {}  # user_id -> BaseUser
        self._named: dict[str, BaseUser] = {}  # config_name -> BaseUser

    def add_user(self, user_id: str, user: BaseUser, config_name: str | None = None) -> None:
        self._users[user_id] = user
        if config_name:
            self._named[config_name] = user

    def get(self, name: str, default=None) -> BaseUser | None:
        user = self._named.get(name) or self._users.get(name)
        if user is None or isinstance(user, UndefinedUser):
            return default
        return user

    def get_user_by_id(self, user_id: int | str) -> BaseUser | None:
        return self._users.get(str(user_id))

    def get_assignable_users(self) -> list[dict]:
        result = []
        for config_name, user in self._named.items():
            if not user.exists:
                continue
            result.append({
                'user_id': str(user.id) if user.id is not None else '',
                'full_name': user.full_name or user.name or '',
                'config_name': config_name,
            })
        return result

    def get_user_timezone(self, user_id: str) -> str | None:
        user = self.get_user_by_id(user_id)
        if user and user.timezone:
            return user.timezone
        return None

    def serialize(self) -> dict[str, dict]:
        return {name: user.serialize() for name, user in sorted(self._named.items())}

    def serialize_one(self, name: str) -> dict | None:
        user = self._named.get(name)
        return user.serialize() if user else None
