from app.im.users import BaseUser


class User(BaseUser):
    """Mattermost-specific user implementation."""

    def __init__(
        self,
        name: str,
        id_: str = None,
        username: str = None,
        exists: bool = False,
        full_name: str = None,
        email: str = None,
        timezone_: str = None,
    ):
        super().__init__(name=name, id_=id_, exists=exists, full_name=full_name, username=username, timezone=timezone_)
        self.email = email

    def get_notification_identifier(self):
        return self.username

    def serialize(self):
        return {
            'email': self.email,
            'full_name': self.full_name,
            'id': str(self.id),
            'name': self.name,
            'timezone': self.timezone,
            'username': self.username,
        }
