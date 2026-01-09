from app.im.users import BaseUser


class User(BaseUser):
    """Mattermost-specific user implementation."""
    
    def __init__(self, name: str, id_: str = None, username: str = None, exists: bool = False):
        super().__init__(name, id_, exists)
        self.username = username
    
    def get_notification_identifier(self):
        """Return username for Mattermost @ mentions."""
        return self.username
