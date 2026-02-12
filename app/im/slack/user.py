from app.im.users import BaseUser


class User(BaseUser):
    """Slack-specific user implementation."""
    
    def __init__(self, name: str, id_: str = None, exists: bool = False, full_name: str = None, username: str = None, timezone_: str = None):
        super().__init__(name, id_, exists, full_name, username, timezone_)
    
    def get_notification_identifier(self):
        return self.id
