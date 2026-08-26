from app.im.users import BaseUser


class User(BaseUser):
    """Slack-specific user implementation."""

    def __init__(
        self,
        name: str,
        id_: str | None = None,
        exists: bool = False,
        full_name: str | None = None,
        username: str | None = None,
        email: str | None = None,
        timezone_: str | None = None,
    ):
        super().__init__(name, id_, exists, full_name, username, timezone_)
        self.email = email

    def get_notification_identifier(self):
        return self.id

    def serialize(self):
        return {
            'email': self.email,
            'exists': self.exists,
            'full_name': self.full_name,
            'id': str(self.id),
            'roles': list(self.roles),
            'timezone': self.timezone,
            'username': self.username,
        }
