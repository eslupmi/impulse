from abc import ABC, abstractmethod

_USE_PLATFORM_ID = object()


class BaseUser(ABC):
    """Base class for all messenger users."""
    
    def __init__(
        self,
        name: str,
        id_: int | str | None = None,
        exists: bool = False,
        full_name: str | None = None,
        username: str | None = None,
        timezone: str | None = None,
        roles: list[str] | None = None,
    ):
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


class UserManager:
    def __init__(self):
        self._users: dict[str, BaseUser] = {}  # user_id -> BaseUser
        self._named: dict[str, BaseUser] = {}  # config_name -> BaseUser

    def add_user(self, user_id: str, user: BaseUser, config_name: str | None = None) -> None:
        self._users[user_id] = user
        if config_name:
            self._named[config_name] = user

    def get(self, name: str, default=None) -> BaseUser | None:
        return self._named.get(name) or self._users.get(name) or default

    def get_user_by_id(self, user_id: int | str) -> BaseUser | None:
        return self._users.get(str(user_id))

    def get_assignable_users(self) -> list[dict]:
        result = []
        for config_name, user in self._named.items():
            if not user.exists:
                continue
            result.append({
                'user_id': str(user.id),
                'full_name': user.full_name or user.name or str(user.id),
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


class ProfileUser(BaseUser):
    """Core cached user backed by a normalized provider profile."""

    def __init__(
        self,
        name: str,
        id_: str | None = None,
        exists: bool = False,
        full_name: str | None = None,
        username: str | None = None,
        email: str | None = None,
        timezone_: str | None = None,
        notification_id=_USE_PLATFORM_ID,
        serializer=None,
    ):
        super().__init__(name, id_, exists, full_name, username, timezone_)
        self.email = email
        self.notification_id = id_ if notification_id is _USE_PLATFORM_ID else notification_id
        self._serializer = serializer

    def get_notification_identifier(self):
        return self.notification_id

    def serialize(self):
        if self._serializer is not None:
            from app.im.plugin_api import UserProfile
            return self._serializer(UserProfile(self.id, self.exists, self.full_name, self.username, self.email, self.timezone), self.roles)
        return {
            'email': self.email,
            'exists': self.exists,
            'full_name': self.full_name,
            'id': str(self.id),
            'roles': list(self.roles),
            'timezone': self.timezone,
            'username': self.username,
        }
