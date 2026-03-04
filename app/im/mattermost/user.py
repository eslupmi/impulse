from app.im.users import BaseUser


class User(BaseUser):
    """Mattermost-specific user implementation."""
    
    def __init__(
        self, name: str, id_: str = None, username: str = None, exists: bool = False, full_name: str = None,
        timezone_: str = None
    ):
        super().__init__(name=name, id_=id_, exists=exists, full_name=full_name, username=username, timezone=timezone_)

    def get_notification_identifier(self):
        return self.username
