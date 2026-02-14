"""
Unit tests for app.queue.handlers.user_update_handler module.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch

import pytest

from app.queue.handlers.user_update_handler import UserUpdateHandler
from app.im.user_store import USER_REFRESH_HOURS
from app.queue.constants import QueueItemType


class TestUserUpdateHandler:
    """Test cases for UserUpdateHandler class."""

    @pytest.fixture
    def mock_queue(self):
        """Create a mock queue."""
        queue = AsyncMock()
        queue.put = AsyncMock()
        queue.get_latest_item_by_type = AsyncMock(return_value=None)
        return queue

    @pytest.fixture
    def mock_application(self):
        """Create a mock application."""
        app = Mock()
        app.type = Mock()
        app.type.value = "slack"
        app.get_user_details = AsyncMock()
        app.create_user = Mock()
        app.users = Mock()
        app.users.add_user = Mock()
        return app

    @pytest.fixture
    def mock_incidents(self):
        """Create a mock incidents collection."""
        return Mock()

    @pytest.fixture
    def handler(self, mock_queue, mock_application, mock_incidents):
        """Create a UserUpdateHandler instance."""
        return UserUpdateHandler(mock_queue, mock_application, mock_incidents)

    def test_handler_initialization(self, mock_queue, mock_application, mock_incidents):
        """Test UserUpdateHandler initialization."""
        handler = UserUpdateHandler(mock_queue, mock_application, mock_incidents)
        
        assert handler.queue == mock_queue
        assert handler.app == mock_application
        assert handler.incidents == mock_incidents

    @pytest.mark.asyncio
    async def test_handle_empty_user_id(self, handler, mock_queue, mock_application):
        """Test handle with empty user_id logs warning and returns."""
        with patch('app.queue.handlers.user_update_handler.get_user_store') as mock_store:
            await handler.handle("")
            
            mock_application.get_user_details.assert_not_called()
            mock_store.return_value.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_user_not_found(self, handler, mock_queue, mock_application):
        """Test handle when user not found in messenger still schedules next refresh."""
        user_id = "U123456"
        mock_application.get_user_details.return_value = {'exists': False}
        
        mock_user_store = Mock()
        
        with patch('app.queue.handlers.user_update_handler.get_user_store', return_value=mock_user_store):
            await handler.handle(user_id)
        
        # Should not save to user store
        mock_user_store.save.assert_not_called()
        
        # Should still schedule next refresh
        mock_queue.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_api_exception(self, handler, mock_queue, mock_application):
        """Test handle with API exception still schedules next refresh."""
        user_id = "U123456"
        mock_application.get_user_details.side_effect = Exception("API Error")
        
        mock_user_store = Mock()
        
        with patch('app.queue.handlers.user_update_handler.get_user_store', return_value=mock_user_store):
            await handler.handle(user_id)
        
        # Should not save to user store
        mock_user_store.save.assert_not_called()
        
        # Should still schedule next refresh (resilient to errors)
        mock_queue.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_next_refresh_timing(self, handler, mock_queue, mock_application):
        """Test _schedule_next_refresh schedules at correct time."""
        user_id = "U123456"
        mock_queue.get_latest_item_by_type.return_value = None
        
        await handler._schedule_next_refresh(user_id)
        
        mock_queue.put.assert_called_once()
        call_args = mock_queue.put.call_args
        schedule_time = call_args[0][0]
        
        # Should be scheduled approximately 12 hours from now
        expected_min = datetime.now(timezone.utc) + timedelta(hours=USER_REFRESH_HOURS - 0.1)
        expected_max = datetime.now(timezone.utc) + timedelta(hours=USER_REFRESH_HOURS + 0.1)
        
        assert expected_min < schedule_time < expected_max

    @pytest.mark.asyncio
    async def test_schedule_next_refresh_with_existing_item(self, handler, mock_queue, mock_application):
        """Test _schedule_next_refresh respects gap from existing item."""
        from app.queue.constants import USER_UPDATE_GAP_SECONDS
        
        user_id = "U123456"
        # Latest item is scheduled far in the future
        future_time = datetime.now(timezone.utc) + timedelta(hours=USER_REFRESH_HOURS + 1)
        mock_queue.get_latest_item_by_type.return_value = future_time
        
        await handler._schedule_next_refresh(user_id)
        
        mock_queue.put.assert_called_once()
        call_args = mock_queue.put.call_args
        schedule_time = call_args[0][0]
        
        # Should be scheduled after the latest item plus gap
        expected_gap = USER_UPDATE_GAP_SECONDS.get("slack", 1.0)
        expected_min = future_time + timedelta(seconds=expected_gap - 0.1)
        
        assert schedule_time >= expected_min

    @pytest.mark.asyncio
    async def test_schedule_next_refresh_queue_item_type(self, handler, mock_queue, mock_application):
        """Test _schedule_next_refresh uses correct queue item type."""
        user_id = "U123456"
        
        await handler._schedule_next_refresh(user_id)
        
        mock_queue.put.assert_called_once()
        call_args = mock_queue.put.call_args
        queue_item_type = call_args[0][1]
        
        assert queue_item_type == QueueItemType.UPDATE_USER

    @pytest.mark.asyncio
    async def test_handle_different_messenger_types(self, mock_queue, mock_incidents):
        """Test handle uses correct messenger type for saving."""
        for messenger_type in ["slack", "telegram", "mattermost"]:
            mock_app = Mock()
            mock_app.type.value = messenger_type
            mock_app.get_user_details = AsyncMock(return_value={
                'exists': True,
                'full_name': 'Test'
            })
            mock_app.create_user = Mock(return_value=Mock())
            mock_app.users = Mock()
            
            handler = UserUpdateHandler(mock_queue, mock_app, mock_incidents)
            
            mock_user_store = Mock()
            
            with patch('app.queue.handlers.user_update_handler.get_user_store', return_value=mock_user_store):
                await handler.handle("user123")
            
            # Verify correct messenger type passed to save
            save_call = mock_user_store.save.call_args
            assert save_call[0][1] == messenger_type
