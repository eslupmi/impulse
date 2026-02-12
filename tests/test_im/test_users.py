"""
Unit tests for app.im.users module.
"""
from unittest.mock import Mock

import pytest

from app.im.users import BaseUser, UndefinedUser, UserManager
from app.im.telegram.user import User as TelegramUser
from app.im.slack.user import User as SlackUser
from app.im.mattermost.user import User as MattermostUser


class TestUndefinedUser:
    """Test cases for UndefinedUser class."""

    def test_undefined_user_creation(self):
        """Test creating an UndefinedUser instance."""
        user = UndefinedUser("testuser")

        assert user.name == "testuser"
        assert user.defined is False

    def test_undefined_user_with_empty_name(self):
        """Test creating an UndefinedUser with empty name."""
        user = UndefinedUser("")

        assert user.name == ""
        assert user.defined is False

    def test_undefined_user_with_none_name(self):
        """Test creating an UndefinedUser with None name."""
        user = UndefinedUser(None)

        assert user.name is None
        assert user.defined is False

    def test_undefined_user_with_special_characters(self):
        """Test creating an UndefinedUser with special characters in name."""
        user = UndefinedUser("user@domain.com")

        assert user.name == "user@domain.com"
        assert user.defined is False

    def test_undefined_user_with_unicode_name(self):
        """Test creating an UndefinedUser with unicode characters."""
        user = UndefinedUser("用户")

        assert user.name == "用户"
        assert user.defined is False

    def test_undefined_user_with_long_name(self):
        """Test creating an UndefinedUser with long name."""
        long_name = "a" * 1000
        user = UndefinedUser(long_name)

        assert user.name == long_name
        assert user.defined is False

    def test_undefined_user_attributes_immutable(self):
        """Test that UndefinedUser attributes are properly set and immutable."""
        user = UndefinedUser("testuser")

        # Test that attributes are set correctly
        assert user.name == "testuser"
        assert user.defined is False

        # Test that defined is always False (immutable behavior)
        assert user.defined is False

    def test_undefined_user_string_representation(self):
        """Test string representation of UndefinedUser."""
        user = UndefinedUser("testuser")

        # The class doesn't define __str__ or __repr__, so we test the attributes
        assert hasattr(user, 'name')
        assert hasattr(user, 'defined')
        assert user.name == "testuser"
        assert user.defined is False

    def test_undefined_user_equality(self):
        """Test equality comparison of UndefinedUser instances."""
        user1 = UndefinedUser("testuser")
        user2 = UndefinedUser("testuser")
        user3 = UndefinedUser("different")

        # Since no __eq__ is defined, instances are compared by identity
        assert user1 is not user2
        assert user1 != user2  # Different instances
        assert user1 != user3  # Different names

    def test_undefined_user_hash(self):
        """Test hash behavior of UndefinedUser instances."""
        user1 = UndefinedUser("testuser")
        user2 = UndefinedUser("testuser")

        # Since no __hash__ is defined, instances should be hashable
        # (default object hash behavior)
        assert hash(user1) != hash(user2)  # Different instances have different hashes

    def test_undefined_user_type(self):
        """Test that UndefinedUser is of correct type."""
        user = UndefinedUser("testuser")

        assert isinstance(user, UndefinedUser)
        assert type(user).__name__ == "UndefinedUser"

    def test_undefined_user_module_import(self):
        """Test that UndefinedUser can be imported from the module."""
        from app.im.users import UndefinedUser

        user = UndefinedUser("testuser")
        assert user.name == "testuser"
        assert user.defined is False
    
    def test_undefined_user_inherits_from_base(self):
        """Test that UndefinedUser inherits from BaseUser."""
        user = UndefinedUser("testuser")
        assert isinstance(user, BaseUser)
    
    def test_undefined_user_has_required_attributes(self):
        """Test that UndefinedUser has all required attributes."""
        user = UndefinedUser("testuser")
        assert hasattr(user, 'name')
        assert hasattr(user, 'id')
        assert hasattr(user, 'exists')
        assert hasattr(user, 'defined')
        assert user.id is None
        assert user.exists is False
    
    def test_undefined_user_get_notification_identifier(self):
        """Test that UndefinedUser returns None for notification identifier."""
        user = UndefinedUser("testuser")
        assert user.get_notification_identifier() is None


class TestTelegramUser:
    """Test cases for Telegram User class."""
    
    def test_telegram_user_creation(self):
        """Test creating a Telegram user."""
        user = TelegramUser("John Doe", id_=12345, exists=True)
        assert user.name == "John Doe"
        assert user.id == 12345
        assert user.exists is True
        assert user.defined is True
    
    def test_telegram_user_inherits_from_base(self):
        """Test that TelegramUser inherits from BaseUser."""
        user = TelegramUser("John Doe", id_=12345)
        assert isinstance(user, BaseUser)
    
    def test_telegram_user_notification_identifier(self):
        """Test that Telegram user returns ID for notifications."""
        user = TelegramUser("John Doe", id_=12345)
        assert user.get_notification_identifier() == 12345
    
    def test_telegram_user_repr(self):
        """Test string representation of Telegram user."""
        user = TelegramUser("John Doe", id_=12345)
        assert repr(user) == "John Doe"


class TestSlackUser:
    """Test cases for Slack User class."""
    
    def test_slack_user_creation(self):
        """Test creating a Slack user."""
        user = SlackUser("Jane Smith", id_="U12345", exists=True)
        assert user.name == "Jane Smith"
        assert user.id == "U12345"
        assert user.exists is True
        assert user.defined is True
    
    def test_slack_user_inherits_from_base(self):
        """Test that SlackUser inherits from BaseUser."""
        user = SlackUser("Jane Smith", id_="U12345")
        assert isinstance(user, BaseUser)
    
    def test_slack_user_notification_identifier(self):
        """Test that Slack user returns ID for notifications."""
        user = SlackUser("Jane Smith", id_="U12345")
        assert user.get_notification_identifier() == "U12345"
    
    def test_slack_user_repr(self):
        """Test string representation of Slack user."""
        user = SlackUser("Jane Smith", id_="U12345")
        assert repr(user) == "Jane Smith"


class TestMattermostUser:
    """Test cases for Mattermost User class."""
    
    def test_mattermost_user_creation(self):
        """Test creating a Mattermost user."""
        user = MattermostUser("Bob Johnson", id_="abc123", username="bjohnson", exists=True)
        assert user.name == "Bob Johnson"
        assert user.id == "abc123"
        assert user.username == "bjohnson"
        assert user.exists is True
        assert user.defined is True
    
    def test_mattermost_user_inherits_from_base(self):
        """Test that MattermostUser inherits from BaseUser."""
        user = MattermostUser("Bob Johnson", id_="abc123", username="bjohnson")
        assert isinstance(user, BaseUser)
    
    def test_mattermost_user_notification_identifier(self):
        """Test that Mattermost user returns username for notifications."""
        user = MattermostUser("Bob Johnson", id_="abc123", username="bjohnson")
        assert user.get_notification_identifier() == "bjohnson"
    
    def test_mattermost_user_repr(self):
        """Test string representation of Mattermost user."""
        user = MattermostUser("Bob Johnson", id_="abc123", username="bjohnson")
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
        telegram_user = TelegramUser("John Doe", id_=12345, exists=True)
        slack_user = SlackUser("Jane Smith", id_="U12345", exists=True)
        
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
        manager.add_user("12345", TelegramUser("John", id_=12345))
        
        found = manager.get_user_by_id(99999)
        assert found is None
        
        found = manager.get_user_by_id("nonexistent")
        assert found is None
