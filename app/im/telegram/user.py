from app.im.users import BaseUser


class User(BaseUser):
    """Telegram-specific user implementation."""

    def __init__(
        self,
        name: str,
        id_: int = None,
        exists: bool = False,
        full_name: str = None,
        username: str = None,
        timezone_: str = None,
    ):
        if id_ is not None and not isinstance(id_, int):
            id_ = int(id_)
        super().__init__(name, id_, exists, full_name, username, timezone_)

    def get_notification_identifier(self):
        return self.id

    def serialize(self):
        return {
            'exists': self.exists,
            'full_name': self.full_name,
            'id': self.id,
            'roles': list(self.roles),
            'username': self.username,
        }
