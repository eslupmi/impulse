"""
Unit tests for app.im.user_store module.
"""
import os
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch

import pytest
import yaml

from app.im.user_store import UserStore, get_user_store, UserUpdateScheduler, USER_REFRESH_HOURS


class TestUserStore:
    """Test cases for UserStore class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def user_store(self, temp_dir):
        """Create a UserStore instance with a temporary directory."""
        with patch('app.im.user_store.get_environment_config') as mock_env:
            mock_env.return_value.data_path = temp_dir
            store = UserStore()
            yield store

    def test_user_store_initialization(self, user_store, temp_dir):
        """Test UserStore initialization creates users directory."""
        users_path = os.path.join(temp_dir, 'users')
        assert os.path.exists(users_path)

    def test_get_nonexistent_user(self, user_store):
        """Test getting a user that doesn't exist returns None."""
        result = user_store.get("nonexistent_user")
        assert result is None

    def test_save_sanitizes_user_id(self, user_store):
        """Test that user IDs with special characters are sanitized."""
        user_id = "user/with\\slashes"
        user_store.save(user_id, "slack", {'username': 'test'})
        
        # File should exist with sanitized name
        result = user_store.get(user_id)
        assert result is not None
        assert result['username'] == 'test'

    def test_is_expired_for_fresh_data(self, user_store):
        """Test is_expired returns False for fresh data."""
        user_id = "U123456"
        user_store.save(user_id, "slack", {'username': 'test'})
        
        assert user_store.is_expired(user_id) is False

    def test_is_expired_for_old_data(self, user_store, temp_dir):
        """Test is_expired returns True for old data."""
        user_id = "U123456"
        
        # Create file with old updated_at
        old_time = datetime.now(timezone.utc) - timedelta(hours=USER_REFRESH_HOURS + 1)
        data = {
            'updated_at': old_time,
            'messenger_type': 'slack',
            'username': 'test'
        }
        
        file_path = os.path.join(temp_dir, 'users', f'{user_id}.yml')
        with open(file_path, 'w') as f:
            yaml.dump(data, f)
        
        assert user_store.is_expired(user_id) is True

    def test_is_expired_for_nonexistent_user(self, user_store):
        """Test is_expired returns True for nonexistent user."""
        assert user_store.is_expired("nonexistent") is True

    def test_is_data_expired_with_missing_updated_at(self, user_store):
        """Test _is_data_expired returns True when updated_at is missing."""
        data = {'username': 'test'}
        assert user_store.is_data_expired(data) is True

    def test_is_data_expired_with_invalid_updated_at(self, user_store):
        """Test _is_data_expired returns True for invalid updated_at."""
        data = {'updated_at': 'invalid-date'}
        assert user_store.is_data_expired(data) is True

    def test_get_next_refresh_time(self, user_store):
        """Test get_next_refresh_time calculates correctly."""
        user_id = "U123456"
        user_store.save(user_id, "slack", {'username': 'test'})
        
        refresh_time = user_store.get_next_refresh_time(user_id)
        expected_min = datetime.now(timezone.utc) + timedelta(hours=USER_REFRESH_HOURS - 0.1)
        expected_max = datetime.now(timezone.utc) + timedelta(hours=USER_REFRESH_HOURS + 0.1)
        
        assert expected_min < refresh_time < expected_max

    def test_get_next_refresh_time_nonexistent_user(self, user_store):
        """Test get_next_refresh_time returns now for nonexistent user."""
        now = datetime.now(timezone.utc)
        refresh_time = user_store.get_next_refresh_time("nonexistent")
        
        # Should be approximately now
        assert abs((refresh_time - now).total_seconds()) < 2

    def test_get_refresh_time_from_data_with_string_date(self, user_store):
        """Test _get_refresh_time_from_data handles string dates."""
        now = datetime.now(timezone.utc)
        data = {'updated_at': now.isoformat()}
        
        refresh_time = user_store.get_refresh_time_from_data(data)
        expected = now + timedelta(hours=USER_REFRESH_HOURS)
        
        assert abs((refresh_time - expected).total_seconds()) < 2

    def test_get_all_users_by_type(self, user_store):
        """Test get_all_users_by_type filters by messenger type."""
        user_store.save("slack_user1", "slack", {'username': 'slack1'})
        user_store.save("slack_user2", "slack", {'username': 'slack2'})
        user_store.save("telegram_user1", "telegram", {'username': 'tg1'})
        
        slack_users = user_store.get_all_users_by_type("slack")
        telegram_users = user_store.get_all_users_by_type("telegram")
        
        assert len(slack_users) == 2
        assert len(telegram_users) == 1
        assert "slack_user1" in slack_users
        assert "slack_user2" in slack_users
        assert "telegram_user1" in telegram_users

    def test_get_all_users_by_type_empty_directory(self, user_store):
        """Test get_all_users_by_type returns empty dict for no users."""
        users = user_store.get_all_users_by_type("slack")
        assert users == {}

    def test_save_with_none_values(self, user_store):
        """Test save handles None values in user_data."""
        user_store.save("U123", "slack", {
            'username': None,
            'email': None,
            'first_name': None,
            'last_name': None,
            'timezone': None
        })
        
        retrieved = user_store.get("U123")
        assert retrieved['username'] is None
        assert retrieved['email'] is None


class TestGetUserStore:
    """Test cases for get_user_store singleton function."""

    def test_get_user_store_returns_singleton(self):
        """Test that get_user_store returns the same instance."""
        with patch('app.im.user_store._user_store', None):
            with patch('app.im.user_store.UserStore') as mock_store_class:
                mock_instance = Mock()
                mock_store_class.return_value = mock_instance
                
                # First call creates instance
                store1 = get_user_store()
                # Second call returns same instance
                store2 = get_user_store()
                
                assert store1 is store2
                mock_store_class.assert_called_once()


class TestUserUpdateScheduler:
    """Test cases for UserUpdateScheduler class."""

    @pytest.fixture
    def mock_queue(self):
        """Create a mock queue."""
        queue = AsyncMock()
        queue.put = AsyncMock()
        queue.get_latest_item_by_type = AsyncMock(return_value=None)
        return queue

    def test_scheduler_initialization(self, mock_queue):
        """Test UserUpdateScheduler initialization."""
        scheduler = UserUpdateScheduler(mock_queue, "slack")
        
        assert scheduler._queue is mock_queue
        assert scheduler._messenger_type == "slack"
        assert abs(scheduler._gap_seconds - 1.0) < 0.01  # Slack gap

    @pytest.mark.asyncio
    async def test_schedule_all_stored_no_users(self, mock_queue):
        """Test schedule_all_stored with no stored users."""
        mock_user_store = Mock()
        mock_user_store.get_all_users_by_type.return_value = {}
        
        scheduler = UserUpdateScheduler(mock_queue, "slack")
        
        with patch('app.im.user_store.get_user_store', return_value=mock_user_store):
            await scheduler.schedule_all_stored()
        
        mock_queue.put.assert_not_called()

    @pytest.mark.asyncio
    async def test_schedule_all_stored_expired_users(self, mock_queue):
        """Test schedule_all_stored schedules expired users with gaps."""
        old_time = datetime.now(timezone.utc) - timedelta(hours=USER_REFRESH_HOURS + 1)
        
        mock_user_store = Mock()
        mock_user_store.get_all_users_by_type.return_value = {
            'user1': {'updated_at': old_time, 'username': 'u1'},
            'user2': {'updated_at': old_time, 'username': 'u2'}
        }
        mock_user_store._is_data_expired.return_value = True
        
        scheduler = UserUpdateScheduler(mock_queue, "slack")
        
        with patch('app.im.user_store.get_user_store', return_value=mock_user_store):
            await scheduler.schedule_all_stored()
        
        assert mock_queue.put.call_count == 2

    @pytest.mark.asyncio
    async def test_schedule_all_stored_uses_messenger_gap(self, mock_queue):
        """Test schedule_all_stored uses correct gap for messenger type."""
        from app.queue.constants import USER_UPDATE_GAP_SECONDS
        
        for messenger_type, expected_gap in USER_UPDATE_GAP_SECONDS.items():
            old_time = datetime.now(timezone.utc) - timedelta(hours=USER_REFRESH_HOURS + 1)
            mock_user_store = Mock()
            mock_user_store.get_all_users_by_type.return_value = {
                'user1': {'updated_at': old_time},
                'user2': {'updated_at': old_time}
            }
            mock_user_store._is_data_expired.return_value = True
            
            mock_queue.reset_mock()
            scheduler = UserUpdateScheduler(mock_queue, messenger_type)
            
            with patch('app.im.user_store.get_user_store', return_value=mock_user_store):
                await scheduler.schedule_all_stored()
            
            assert mock_queue.put.call_count == 2
            call1_time = mock_queue.put.call_args_list[0][0][0]
            call2_time = mock_queue.put.call_args_list[1][0][0]
            gap = (call2_time - call1_time).total_seconds()
            assert abs(gap - expected_gap) < 0.1

    @pytest.mark.asyncio
    async def test_schedule_update_single_user(self, mock_queue):
        """Test schedule_update schedules a single user update."""
        import asyncio
        
        scheduler = UserUpdateScheduler(mock_queue, "slack")
        scheduler.schedule_update("user123")
        
        await asyncio.sleep(0.1)
        
        mock_queue.put.assert_called_once()
        call_args = mock_queue.put.call_args
        assert call_args[1]['identifier'] == "user123"

    @pytest.mark.asyncio
    async def test_schedule_update_respects_gap(self, mock_queue):
        """Test schedule_update respects gap from latest queue item."""
        import asyncio
        from app.queue.constants import USER_UPDATE_GAP_SECONDS
        
        future_time = datetime.now(timezone.utc) + timedelta(minutes=5)
        mock_queue.get_latest_item_by_type = AsyncMock(return_value=future_time)
        
        scheduler = UserUpdateScheduler(mock_queue, "slack")
        scheduler.schedule_update("user123")
        
        await asyncio.sleep(0.1)
        
        mock_queue.put.assert_called_once()
        call_args = mock_queue.put.call_args
        schedule_time = call_args[0][0]
        
        expected_gap = USER_UPDATE_GAP_SECONDS.get("slack", 1.0)
        expected_min = future_time + timedelta(seconds=expected_gap - 0.1)
        assert schedule_time >= expected_min

    @pytest.mark.asyncio
    async def test_schedule_update_tracks_tasks(self, mock_queue):
        """Test schedule_update tracks tasks to prevent GC."""
        import asyncio
        
        scheduler = UserUpdateScheduler(mock_queue, "slack")
        
        initial_tasks = len(scheduler._async_tasks)
        scheduler.schedule_update("user123")
        
        assert len(scheduler._async_tasks) >= initial_tasks
        
        await asyncio.sleep(0.1)
        
        assert len(scheduler._async_tasks) == 0
