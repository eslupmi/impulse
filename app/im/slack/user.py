from app.im.users import BaseUser


class User(BaseUser):
    """Slack-specific user implementation."""
    
    def __init__(self, name: str, id_: str = None, exists: bool = False, timezone: str = None):
        super().__init__(name, id_, exists, timezone)
    
    def get_notification_identifier(self):
        """Return user ID for Slack mentions."""
        return self.id
