"""
Unit tests for app.im.users module.
"""
from app.im.users import ProfileUser, UserManager


class TestProfileUserNumericMentions:
    def test_numeric_mention_identifier(self):
        user = ProfileUser('john', id_=12345, exists=True, notification_id=12345)
        assert user.get_notification_identifier() == 12345


class TestProfileUserStringIDs:
    """Cached users with string platform IDs."""
    
    def test_slack_user_creation(self):
        """Test creating a Slack user."""
        user = ProfileUser("Jane Smith", id_="U12345", exists=True)
        assert user.name == "Jane Smith"
        assert user.id == "U12345"
        assert user.exists is True
        assert user.defined is True
    
    def test_slack_user_notification_identifier(self):
        """Test that Slack user returns ID for notifications."""
        user = ProfileUser("Jane Smith", id_="U12345")
        assert user.get_notification_identifier() == "U12345"

    def test_slack_user_serialize(self):
        user = ProfileUser(
            "jane",
            id_="U12345",
            exists=True,
            full_name="Jane Smith",
            username="jane",
            email="jane@example.com",
            timezone_="America/New_York",
        )
        payload = user.serialize()
        assert payload == {
            "email": "jane@example.com",
            "exists": True,
            "full_name": "Jane Smith",
            "id": "U12345",
            "roles": [],
            "timezone": "America/New_York",
            "username": "jane",
        }
        assert isinstance(payload["id"], str)
        assert list(payload) == sorted(payload)
    
    def test_slack_user_repr(self):
        """Test string representation of Slack user."""
        user = ProfileUser("Jane Smith", id_="U12345")
        assert repr(user) == "Jane Smith"


class TestProfileUserUsernameMentions:
    """Cached users whose notification identifier is a username."""
    
    def test_mattermost_user_creation(self):
        """Test creating a Mattermost user."""
        user = ProfileUser("Bob Johnson", id_="abc123", username="bjohnson", exists=True, notification_id="bjohnson")
        assert user.name == "Bob Johnson"
        assert user.id == "abc123"
        assert user.username == "bjohnson"
        assert user.exists is True
        assert user.defined is True
    
    def test_mattermost_user_notification_identifier(self):
        """Test that Mattermost user returns username for notifications."""
        user = ProfileUser("Bob Johnson", id_="abc123", username="bjohnson", notification_id="bjohnson")
        assert user.get_notification_identifier() == "bjohnson"

    def test_mattermost_user_serialize(self):
        user = ProfileUser(
            "bob",
            id_="abc123",
            username="bjohnson",
            exists=True,
            full_name="Bob Johnson",
            email="bob@example.com",
            timezone_="UTC",
            notification_id="bjohnson",
        )
        payload = user.serialize()
        assert payload == {
            "email": "bob@example.com",
            "exists": True,
            "full_name": "Bob Johnson",
            "id": "abc123",
            "roles": [],
            "timezone": "UTC",
            "username": "bjohnson",
        }
        assert isinstance(payload["id"], str)
        assert list(payload) == sorted(payload)
    
    def test_mattermost_user_repr(self):
        """Test string representation of Mattermost user."""
        user = ProfileUser("Bob Johnson", id_="abc123", username="bjohnson", notification_id="bjohnson")
        assert repr(user) == "Bob Johnson"


class TestUserManager:
    """Test cases for UserManager class."""
    
    def test_user_manager_creation(self):
        """Test creating a UserManager instance."""
        manager = UserManager()
        assert isinstance(manager, UserManager)
    
    def test_get_user_by_id_found(self):
        """Test finding a user by their platform ID."""
        manager = UserManager()
        telegram_user = ProfileUser("John Doe", id_=12345, exists=True)
        slack_user = ProfileUser("Jane Smith", id_="U12345", exists=True)
        
        manager.add_user("12345", telegram_user, config_name="john")
        manager.add_user("U12345", slack_user, config_name="jane")
        
        # Find by integer ID (Telegram)
        found = manager.get_user_by_id(12345)
        assert found is not None
        assert found.name == "John Doe"
        assert found == telegram_user
        
        # Find by string ID (Slack)
        found = manager.get_user_by_id("U12345")
        assert found is not None
        assert found.name == "Jane Smith"
        assert found == slack_user
    
    def test_get_user_by_id_not_found(self):
        """Test get_user_by_id returns None when user not found."""
        manager = UserManager()
        manager.add_user("12345", ProfileUser("John", id_=12345))
        
        found = manager.get_user_by_id(99999)
        assert found is None
        
        found = manager.get_user_by_id("nonexistent")
        assert found is None
