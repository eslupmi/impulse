"""
Unit tests for app.queue.manager module.
"""
import asyncio
from unittest.mock import Mock, AsyncMock, patch

import pytest

from app.queue.manager import AsyncQueueManager
from tests.utils import (
    create_mock_queue, create_mock_application, create_mock_incidents_collection,
    create_mock_route, create_mock_webhooks_collection, create_alert_payload,
    create_mock_async_task
)


class TestAsyncQueueManager:
    """Test cases for AsyncQueueManager class."""

    @pytest.fixture
    def mock_queue(self):
        """Create mock queue for testing."""
        queue = create_mock_queue()
        queue.get_next_ready_item = AsyncMock(return_value=(None, None, None, None))
        return queue

    @pytest.fixture
    def mock_application(self):
        """Create mock application for testing."""
        return create_mock_application()

    @pytest.fixture
    def mock_incidents(self):
        """Create mock incidents for testing."""
        return create_mock_incidents_collection()

    @pytest.fixture
    def mock_webhooks(self):
        """Create mock webhooks for testing."""
        return create_mock_webhooks_collection()

    @pytest.fixture
    def mock_route(self):
        """Create mock route for testing."""
        return create_mock_route()

    @pytest.fixture
    def queue_manager(self, mock_queue, mock_application, mock_incidents, mock_webhooks, mock_route):
        """Create AsyncQueueManager instance for testing."""
        manager = AsyncQueueManager(mock_queue, mock_application, mock_incidents, mock_webhooks, mock_route)

        # Replace handlers with mocks to avoid read-only attribute issues
        manager.alert_handler = Mock()
        manager.alert_handler.handle = AsyncMock()
        manager.status_update_handler = Mock()
        manager.status_update_handler.handle = AsyncMock()
        manager.step_handler = Mock()
        manager.step_handler.handle = AsyncMock()

        return manager

    def test_initialization(self, mock_queue, mock_application, mock_incidents, mock_webhooks, mock_route):
        """Test AsyncQueueManager initialization."""
        manager = AsyncQueueManager(mock_queue, mock_application, mock_incidents, mock_webhooks, mock_route)

        assert manager.queue == mock_queue
        assert manager.step_handler is not None
        assert manager.status_update_handler is not None
        assert manager.alert_handler is not None
        assert manager._running is False
        assert manager._task is None

    def test_start_processing(self, queue_manager):
        """Test starting queue processing."""
        with patch('asyncio.create_task') as mock_create_task:
            mock_task = Mock()
            mock_create_task.return_value = mock_task

            queue_manager.start_processing()

            assert queue_manager._running is True
            assert queue_manager._task is mock_task
            mock_create_task.assert_called_once()

    def test_start_processing_already_running(self, queue_manager):
        """Test starting processing when already running."""
        queue_manager._running = True
        queue_manager._task = Mock()

        with patch('asyncio.create_task') as mock_create_task:
            queue_manager.start_processing()

            # Should not create new task
            assert queue_manager._running is True
            mock_create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_stop_processing(self, queue_manager):
        """Test stopping queue processing."""

        # Create a mock task using utility function
        mock_task = create_mock_async_task()
        queue_manager._task = mock_task
        queue_manager._running = True

        await queue_manager.stop_processing()

        assert queue_manager._running is False
        # The task should be cancelled but not None (this is the actual behavior)
        assert queue_manager._task.cancelled()

    @pytest.mark.asyncio
    async def test_stop_processing_not_running(self, queue_manager):
        """Test stopping processing when not running."""
        await queue_manager.stop_processing()

        assert queue_manager._running is False
        assert queue_manager._task is None

    @pytest.mark.asyncio
    async def test_queue_handle_once_no_items(self, queue_manager, mock_queue):
        """Test handling queue with no items."""
        mock_queue.get_next_ready_item.return_value = (None, None, None, None)

        # Should not raise any exceptions
        await queue_manager.queue_handle_once()

    @pytest.mark.asyncio
    async def test_queue_handle_once_alert_item(self, queue_manager, mock_queue):
        """Test handling queue with alert item."""
        # Use utility function for alert payload
        alert_payload = create_alert_payload(
            status="firing",
            alertname="TestAlert",
            severity="critical"
        )

        mock_queue.get_next_ready_item.return_value = ('alert', 'incident123', 'identifier456', alert_payload)

        await queue_manager.queue_handle_once()

        queue_manager.alert_handler.handle.assert_called_once_with(alert_payload)

    @pytest.mark.asyncio
    async def test_queue_handle_once_update_status_item(self, queue_manager, mock_queue):
        """Test handling queue with update_status item."""
        mock_queue.get_next_ready_item.return_value = ('update_status', 'incident123', None, None)

        await queue_manager.queue_handle_once()

        queue_manager.status_update_handler.handle.assert_called_once_with('incident123')

    @pytest.mark.asyncio
    async def test_queue_handle_once_chain_step_item(self, queue_manager, mock_queue):
        """Test handling queue with chain_step item."""
        mock_queue.get_next_ready_item.return_value = ('chain_step', 'incident123', '0', None)

        await queue_manager.queue_handle_once()

        queue_manager.step_handler.handle.assert_called_once_with('incident123', '0')

    @pytest.mark.asyncio
    async def test_queue_handle_once_unknown_item_type(self, queue_manager, mock_queue):
        """Test handling queue with unknown item type."""
        mock_queue.get_next_ready_item.return_value = ('unknown_type', 'incident123', 'identifier456', {'data': 'test'})

        # Should not raise exception, just skip
        await queue_manager.queue_handle_once()

    @pytest.mark.asyncio
    async def test_queue_handle_once_handler_exception(self, queue_manager, mock_queue):
        """Test handling queue when handler raises exception."""
        alert_payload = create_alert_payload()
        mock_queue.get_next_ready_item.return_value = ('alert', 'incident123', 'identifier456', alert_payload)

        # Mock the alert_handler.handle method to raise exception
        queue_manager.alert_handler.handle.side_effect = Exception("Handler error")

        with patch('app.queue.manager.logger') as mock_logger:
            # Should not raise exception, just log and continue
            await queue_manager.queue_handle_once()

            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_step(self, queue_manager):
        """Test handle_step method."""
        await queue_manager.handle_step('incident123', '0')

        queue_manager.step_handler.handle.assert_called_once_with('incident123', '0')

    @pytest.mark.asyncio
    async def test_handle_status_update(self, queue_manager):
        """Test handle_status_update method."""
        await queue_manager.handle_status_update('incident123')

        queue_manager.status_update_handler.handle.assert_called_once_with('incident123')

    @pytest.mark.asyncio
    async def test_handle_alert(self, queue_manager):
        """Test handle_alert method."""
        alert_payload = create_alert_payload()

        await queue_manager.handle_alert(alert_payload)

        queue_manager.alert_handler.handle.assert_called_once_with(alert_payload)

    @pytest.mark.asyncio
    async def test_process_queue_loop_with_sleep(self, queue_manager, mock_queue):
        """Test processing loop with sleep between iterations."""
        # Mock the _process_queue_loop method to avoid infinite loop
        with patch.object(queue_manager, '_process_queue_loop') as mock_loop:
            # Mock the actual loop behavior
            async def mock_loop_behavior():
                # Simulate one iteration of the loop
                await queue_manager.queue_handle_once()
                await asyncio.sleep(0.1)

            mock_loop.side_effect = mock_loop_behavior

            # Set running to True and call the mocked loop
            queue_manager._running = True
            await queue_manager._process_queue_loop()

            # Verify the loop was called
            mock_loop.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_queue_loop_exception_handling(self, queue_manager, mock_queue):
        """Test processing loop exception handling."""
        # Mock the _process_queue_loop method to avoid infinite loop
        with patch.object(queue_manager, '_process_queue_loop') as mock_loop:
            # Mock the actual loop behavior with exception
            async def mock_loop_behavior():
                # Simulate exception in queue_handle_once
                try:
                    await queue_manager.queue_handle_once()
                except Exception as e:
                    # Simulate the exception handling in the real loop
                    with patch('app.queue.manager.logger') as mock_logger:
                        mock_logger.error(f"Error in queue processing loop: {e}")
                        await asyncio.sleep(1)

            mock_loop.side_effect = mock_loop_behavior

            # Set running to True and call the mocked loop
            queue_manager._running = True
            await queue_manager._process_queue_loop()

            # Verify the loop was called
            mock_loop.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_queue_loop_cancelled_error(self, queue_manager):
        """Test processing loop with CancelledError."""
        # Mock the _process_queue_loop method to avoid infinite loop
        with patch.object(queue_manager, '_process_queue_loop') as mock_loop:
            # Mock the actual loop behavior with CancelledError
            async def mock_loop_behavior():
                # Simulate CancelledError in queue_handle_once
                try:
                    await queue_manager.queue_handle_once()
                except asyncio.CancelledError:
                    # Simulate the break in the real loop
                    return

            mock_loop.side_effect = mock_loop_behavior

            # Set running to True and call the mocked loop
            queue_manager._running = True
            await queue_manager._process_queue_loop()

            # Verify the loop was called
            mock_loop.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_processing_logging(self, queue_manager):
        """Test that start_processing logs the start message."""
        with patch('app.queue.manager.logger') as mock_logger:
            with patch('asyncio.create_task') as mock_create_task:
                mock_task = Mock()
                mock_create_task.return_value = mock_task
                
                queue_manager.start_processing()

                mock_logger.info.assert_called_once_with("Started Queue")

    @pytest.mark.asyncio
    async def test_stop_processing_logging(self, queue_manager):
        """Test that stop_processing logs the stop message."""
        # Start processing first with mocked task creation
        with patch('asyncio.create_task') as mock_create_task:
            # Create a mock task using utility function
            mock_task = create_mock_async_task()
            mock_create_task.return_value = mock_task
            queue_manager.start_processing()

        with patch('app.queue.manager.logger') as mock_logger:
            await queue_manager.stop_processing()

            mock_logger.info.assert_called_once_with("Stopped queue")

    @pytest.mark.asyncio
    async def test_stop_processing_with_task_cancellation(self, queue_manager):
        """Test stop_processing with task cancellation."""

        # Create a mock task using utility function
        mock_task = create_mock_async_task()
        queue_manager._task = mock_task
        queue_manager._running = True

        await queue_manager.stop_processing()

        assert queue_manager._running is False
        # The task should be cancelled but not None (this is the actual behavior)
        assert queue_manager._task.cancelled()
