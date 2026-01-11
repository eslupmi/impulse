from app.im.users import BaseUser


class User(BaseUser):
    """Slack-specific user implementation."""
    
    def __init__(self, name: str, id_: str = None, exists: bool = False):
        super().__init__(name, id_, exists)
    
    def get_notification_identifier(self):
        """Return user ID for Slack mentions."""
        return self.id
