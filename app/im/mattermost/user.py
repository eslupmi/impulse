from app.im.users import BaseUser


class User(BaseUser):
    """Mattermost-specific user implementation."""
    
    def __init__(self, name: str, id_: str = None, username: str = None, exists: bool = False, timezone: str = None):
        super().__init__(name, id_, exists, timezone)
        self.username = username
    
    def get_notification_identifier(self):
        """Return username for Mattermost @ mentions."""
        return self.username
