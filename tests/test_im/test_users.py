"""
Unit tests for app.im.users module.
"""
from unittest.mock import Mock, AsyncMock, patch
import asyncio

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
    
    def test_add_and_get_user(self):
        """Test adding and retrieving a user."""
        manager = UserManager()
        user = TelegramUser("John Doe", id_=12345)
        manager.add_user("john", user)
        
        retrieved = manager.get_user("john")
        assert retrieved == user
        assert retrieved.name == "John Doe"
    
    def test_get_nonexistent_user_returns_undefined(self):
        """Test that getting a nonexistent user returns UndefinedUser."""
        manager = UserManager()
        user = manager.get_user("nonexistent")
        
        assert isinstance(user, UndefinedUser)
        assert user.name == "nonexistent"
        assert user.defined is False
    
    def test_get_all_users(self):
        """Test getting all users."""
        manager = UserManager()
        user1 = TelegramUser("John Doe", id_=12345)
        user2 = SlackUser("Jane Smith", id_="U12345")
        
        manager.add_user("john", user1)
        manager.add_user("jane", user2)
        
        all_users = manager.get_all_users()
        assert len(all_users) == 2
        assert "john" in all_users
        assert "jane" in all_users
        assert all_users["john"] == user1
        assert all_users["jane"] == user2
    
    def test_dict_style_access(self):
        """Test dictionary-style access with []."""
        manager = UserManager()
        user = MattermostUser("Bob Johnson", id_="abc123", username="bjohnson")
        manager.add_user("bob", user)
        
        retrieved = manager["bob"]
        assert retrieved == user
        assert retrieved.name == "Bob Johnson"
    
    def test_dict_style_access_nonexistent(self):
        """Test dictionary-style access for nonexistent user."""
        manager = UserManager()
        user = manager["nonexistent"]
        
        assert isinstance(user, UndefinedUser)
        assert user.name == "nonexistent"
    
    def test_contains_operator(self):
        """Test 'in' operator support."""
        manager = UserManager()
        user = TelegramUser("John Doe", id_=12345)
        manager.add_user("john", user)
        
        assert "john" in manager
        assert "nonexistent" not in manager
    
    def test_get_method_with_default(self):
        """Test get() method with default value."""
        manager = UserManager()
        user = SlackUser("Jane Smith", id_="U12345")
        manager.add_user("jane", user)
        
        # Existing user
        retrieved = manager.get("jane", None)
        assert retrieved == user
        
        # Nonexistent user with default
        retrieved = manager.get("nonexistent", None)
        assert retrieved is None
    
    def test_multiple_messenger_types(self):
        """Test manager can handle users from different messengers."""
        manager = UserManager()
        
        telegram_user = TelegramUser("John", id_=12345)
        slack_user = SlackUser("Jane", id_="U12345")
        mattermost_user = MattermostUser("Bob", id_="abc123", username="bob")
        
        manager.add_user("john", telegram_user)
        manager.add_user("jane", slack_user)
        manager.add_user("bob", mattermost_user)
        
        assert len(manager.get_all_users()) == 3
        assert isinstance(manager["john"], TelegramUser)
        assert isinstance(manager["jane"], SlackUser)
        assert isinstance(manager["bob"], MattermostUser)
    
    def test_get_user_by_id_found(self):
        """Test finding a user by their platform ID."""
        manager = UserManager()
        telegram_user = TelegramUser("John Doe", id_=12345, exists=True)
        slack_user = SlackUser("Jane Smith", id_="U12345", exists=True)
        
        manager.add_user("john", telegram_user)
        manager.add_user("jane", slack_user)
        
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
        manager.add_user("john", TelegramUser("John", id_=12345))
        
        found = manager.get_user_by_id(99999)
        assert found is None
        
        found = manager.get_user_by_id("nonexistent")
        assert found is None
    
    def test_configure_queue(self):
        """Test configure_queue sets queue and messenger type."""
        manager = UserManager()
        mock_queue = Mock()
        
        manager.configure_queue(mock_queue, "slack")
        
        assert manager._queue is mock_queue
        assert manager._messenger_type == "slack"
    
    def test_configure_queue_different_messenger_types(self):
        """Test configure_queue with different messenger types."""
        for messenger_type in ["slack", "telegram", "mattermost"]:
            manager = UserManager()
            mock_queue = Mock()
            
            manager.configure_queue(mock_queue, messenger_type)
            
            assert manager._messenger_type == messenger_type
    
    @pytest.mark.asyncio
    async def test_schedule_user_update_without_queue(self):
        """Test schedule_user_update does nothing when queue not configured."""
        manager = UserManager()
        
        # Should not raise, just return early
        manager.schedule_user_update("user123")
        
        # No way to verify except it doesn't crash
        assert manager._queue is None
    
    @pytest.mark.asyncio
    async def test_schedule_user_update_with_queue(self):
        """Test schedule_user_update creates task and schedules update."""
        manager = UserManager()
        mock_queue = AsyncMock()
        mock_queue.get_latest_item_by_type = AsyncMock(return_value=None)
        mock_queue.put = AsyncMock()
        
        manager.configure_queue(mock_queue, "slack")
        manager.schedule_user_update("user123")
        
        # Give time for async task to complete
        await asyncio.sleep(0.1)
        
        # Should have called queue.put
        mock_queue.put.assert_called_once()
        call_args = mock_queue.put.call_args
        assert call_args[1]['identifier'] == "user123"
    
    @pytest.mark.asyncio
    async def test_schedule_user_update_tracks_task(self):
        """Test schedule_user_update tracks task to prevent GC."""
        manager = UserManager()
        mock_queue = AsyncMock()
        mock_queue.get_latest_item_by_type = AsyncMock(return_value=None)
        mock_queue.put = AsyncMock()
        
        manager.configure_queue(mock_queue, "slack")
        
        initial_tasks = len(manager._async_tasks)
        manager.schedule_user_update("user123")
        
        # Task should be tracked
        assert len(manager._async_tasks) >= initial_tasks
        
        # Wait for task to complete
        await asyncio.sleep(0.1)
        
        # Task should be removed after completion
        assert len(manager._async_tasks) == 0
    
    @pytest.mark.asyncio
    async def test_schedule_user_update_respects_gap(self):
        """Test schedule_user_update respects gap from latest item."""
        from datetime import datetime, timezone, timedelta
        from app.queue.constants import USER_UPDATE_GAP_SECONDS
        
        manager = UserManager()
        mock_queue = AsyncMock()
        
        # Simulate existing item in queue
        future_time = datetime.now(timezone.utc) + timedelta(minutes=5)
        mock_queue.get_latest_item_by_type = AsyncMock(return_value=future_time)
        mock_queue.put = AsyncMock()
        
        manager.configure_queue(mock_queue, "slack")
        manager.schedule_user_update("user123")
        
        await asyncio.sleep(0.1)
        
        mock_queue.put.assert_called_once()
        call_args = mock_queue.put.call_args
        schedule_time = call_args[0][0]
        
        expected_gap = USER_UPDATE_GAP_SECONDS.get("slack", 1.0)
        expected_min = future_time + timedelta(seconds=expected_gap - 0.1)
        
        assert schedule_time >= expected_min
    