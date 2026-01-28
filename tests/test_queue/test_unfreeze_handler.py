"""
Unit tests for UnfreezeHandler.

This module tests the UnfreezeHandler which handles automatic unfreezing
of incidents when their freeze duration expires.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch

import pytest

from app.queue.handlers.unfreeze_handler import UnfreezeHandler
from app.queue.constants import QueueItemType
from tests.utils import (
    create_mock_queue,
    create_mock_application,
    create_mock_incidents_collection,
    create_mock_incident_for_handlers
)


class TestUnfreezeHandler:
    """Test cases for UnfreezeHandler class."""

    @pytest.fixture
    def mock_queue(self):
        """Create mock queue."""
        queue = create_mock_queue()
        queue.recreate = AsyncMock()
        queue.put = AsyncMock()
        return queue

    @pytest.fixture
    def mock_application(self):
        """Create mock application."""
        app = create_mock_application()
        app.update_thread = AsyncMock()
        app.post_thread = AsyncMock()
        
        # Mock templates
        app.header_template = Mock()
        app.header_template.form_message = Mock(return_value="Test Header")
        app.body_template = Mock()
        app.body_template.form_message = Mock(return_value="Test Body")
        app.status_icons_template = Mock()
        app.status_icons_template.form_message = Mock(return_value="Test Icons")
        
        app.type = Mock()
        app.type.value = "slack"
        
        return app

    @pytest.fixture
    def mock_incidents(self):
        """Create mock incidents collection."""
        incidents = create_mock_incidents_collection()
        incidents.unfreeze_incident = Mock()
        return incidents

    @pytest.fixture
    def unfreeze_handler(self, mock_queue, mock_application, mock_incidents):
        """Create UnfreezeHandler instance for testing."""
        return UnfreezeHandler(mock_queue, mock_application, mock_incidents)

    @pytest.mark.asyncio
    async def test_handler_initialization(self, mock_queue, mock_application, mock_incidents):
        """Test UnfreezeHandler initialization."""
        handler = UnfreezeHandler(mock_queue, mock_application, mock_incidents)

        assert handler.queue == mock_queue
        assert handler.app == mock_application
        assert handler.incidents == mock_incidents

    @pytest.mark.asyncio
    async def test_handle_frozen_incident(self, unfreeze_handler, mock_incidents, mock_application, mock_queue):
        """Test handling unfreeze for a frozen incident."""
        incident_uniq_id = 'incident123'

        # Create mock frozen incident
        frozen_until = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="firing",
            frozen_until=frozen_until
        )
        mock_incident.is_frozen = Mock(return_value=True)
        mock_incident.channel_id = "C123456789"
        mock_incident.ts = "1234567890.123456"
        mock_incident.status_update_datetime = datetime.now(timezone.utc)

        mock_incidents.uniq_ids = {incident_uniq_id: mock_incident}

        await unfreeze_handler.handle(incident_uniq_id)

        # Should call unfreeze_incident
        mock_incidents.unfreeze_incident.assert_called_once_with(incident_uniq_id)

        # Should post notification
        mock_application.post_thread.assert_called_once()

        # Should put STATUS_CHECK in queue
        mock_queue.put_first.assert_called_once()

        # Should recreate queue and put update status
        mock_queue.recreate.assert_called_once()
        mock_queue.put.assert_called_once()

        # Should update thread
        mock_application.update_thread.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_already_unfrozen_incident(self, unfreeze_handler, mock_incidents, mock_application):
        """Test handling unfreeze for an incident that's already unfrozen."""
        incident_uniq_id = 'incident123'

        # Create mock unfrozen incident
        mock_incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="firing",
            frozen_until=None
        )
        mock_incident.is_frozen = Mock(return_value=False)

        mock_incidents.uniq_ids = {incident_uniq_id: mock_incident}

        await unfreeze_handler.handle(incident_uniq_id)

        # Should NOT call unfreeze_incident
        mock_incidents.unfreeze_incident.assert_not_called()

        # Should NOT call app methods
        mock_application.post_thread.assert_not_called()
        mock_application.update_thread.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_nonexistent_incident(self, unfreeze_handler, mock_incidents, mock_application):
        """Test handling unfreeze for non-existent incident."""
        incident_uniq_id = 'nonexistent123'
        mock_incidents.uniq_ids = {}

        # Should not raise an error, just return early
        await unfreeze_handler.handle(incident_uniq_id)

        # Should NOT call any methods
        mock_application.post_thread.assert_not_called()
        mock_application.update_thread.assert_not_called()

    @pytest.mark.asyncio
    async def test_unfreeze_deleted_incident_skips_queue_operations(self, unfreeze_handler, mock_incidents, 
                                                                    mock_application, mock_queue):
        """Test that deleted incidents skip queue recreation."""
        incident_uniq_id = 'incident123'

        # Create mock frozen incident with deleted status
        frozen_until = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="deleted",
            frozen_until=frozen_until
        )
        mock_incident.is_frozen = Mock(return_value=True)
        mock_incident.channel_id = "C123456789"
        mock_incident.ts = "1234567890.123456"

        mock_incidents.uniq_ids = {incident_uniq_id: mock_incident}

        await unfreeze_handler.handle(incident_uniq_id)

        # Should call unfreeze_incident
        mock_incidents.unfreeze_incident.assert_called_once()

        # Should post notification
        mock_application.post_thread.assert_called_once()

        # Should put STATUS_CHECK in queue
        mock_queue.put_first.assert_called_once()

        # Should NOT recreate queue or put update status for deleted incident
        mock_queue.recreate.assert_not_called()
        mock_queue.put.assert_not_called()

        # Should still update thread
        mock_application.update_thread.assert_called_once()

    @pytest.mark.asyncio
    async def test_unfreeze_with_telegram_messenger(self, unfreeze_handler, mock_incidents, 
                                                    mock_application, mock_queue):
        """Test unfreeze with Telegram messenger type."""
        incident_uniq_id = 'incident123'

        # Set messenger type to telegram
        mock_application.type.value = "telegram"

        # Create mock frozen incident
        frozen_until = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="firing",
            frozen_until=frozen_until
        )
        mock_incident.is_frozen = Mock(return_value=True)
        mock_incident.channel_id = "C123456789"
        mock_incident.ts = "1234567890.123456"
        mock_incident.status_update_datetime = datetime.now(timezone.utc)

        mock_incidents.uniq_ids = {incident_uniq_id: mock_incident}

        await unfreeze_handler.handle(incident_uniq_id)

        # Should post notification (message format different for telegram)
        mock_application.post_thread.assert_called_once()
        call_args = mock_application.post_thread.call_args[0]
        # For telegram, message should not include header
        assert call_args[0] == mock_incident.channel_id
        assert call_args[1] == mock_incident.ts

    @pytest.mark.asyncio
    async def test_unfreeze_includes_task_link(self, unfreeze_handler, mock_incidents, 
                                              mock_application, mock_queue):
        """Test that unfreeze includes task link in update."""
        incident_uniq_id = 'incident123'

        # Create mock frozen incident with task link
        frozen_until = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="firing",
            frozen_until=frozen_until
        )
        mock_incident.is_frozen = Mock(return_value=True)
        mock_incident.channel_id = "C123456789"
        mock_incident.ts = "1234567890.123456"
        mock_incident.task_link = "https://jira.com/browse/DTS-123"
        mock_incident.status_update_datetime = datetime.now(timezone.utc)

        mock_incidents.uniq_ids = {incident_uniq_id: mock_incident}

        await unfreeze_handler.handle(incident_uniq_id)

        # Should include task link in update_thread call
        mock_application.update_thread.assert_called_once()
        call_args = mock_application.update_thread.call_args[0]
        assert call_args[8] == "https://jira.com/browse/DTS-123"  # task_link is at index 8

    @pytest.mark.asyncio
    async def test_unfreeze_firing_incident(self, unfreeze_handler, mock_incidents, 
                                           mock_application, mock_queue):
        """Test unfreezing a firing incident."""
        incident_uniq_id = 'incident123'

        frozen_until = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="firing",
            frozen_until=frozen_until
        )
        mock_incident.is_frozen = Mock(return_value=True)
        mock_incident.channel_id = "C123456789"
        mock_incident.ts = "1234567890.123456"
        mock_incident.status_update_datetime = datetime.now(timezone.utc)

        mock_incidents.uniq_ids = {incident_uniq_id: mock_incident}

        await unfreeze_handler.handle(incident_uniq_id)

        # Should unfreeze and recreate queue
        mock_incidents.unfreeze_incident.assert_called_once()
        mock_queue.recreate.assert_called_once()
        mock_queue.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_unfreeze_resolved_incident(self, unfreeze_handler, mock_incidents, 
                                              mock_application, mock_queue):
        """Test unfreezing a resolved incident."""
        incident_uniq_id = 'incident123'

        frozen_until = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="resolved",
            frozen_until=frozen_until
        )
        mock_incident.is_frozen = Mock(return_value=True)
        mock_incident.channel_id = "C123456789"
        mock_incident.ts = "1234567890.123456"
        mock_incident.status_update_datetime = datetime.now(timezone.utc)

        mock_incidents.uniq_ids = {incident_uniq_id: mock_incident}

        await unfreeze_handler.handle(incident_uniq_id)

        # Should unfreeze and recreate queue
        mock_incidents.unfreeze_incident.assert_called_once()
        mock_queue.recreate.assert_called_once()
        mock_queue.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_unfreeze_closed_incident(self, unfreeze_handler, mock_incidents, 
                                           mock_application, mock_queue):
        """Test unfreezing a closed incident."""
        incident_uniq_id = 'incident123'

        frozen_until = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="closed",
            frozen_until=frozen_until
        )
        mock_incident.is_frozen = Mock(return_value=True)
        mock_incident.channel_id = "C123456789"
        mock_incident.ts = "1234567890.123456"
        mock_incident.status_update_datetime = datetime.now(timezone.utc)

        mock_incidents.uniq_ids = {incident_uniq_id: mock_incident}

        await unfreeze_handler.handle(incident_uniq_id)

        # Should unfreeze and recreate queue (closed is not deleted)
        mock_incidents.unfreeze_incident.assert_called_once()
        mock_queue.recreate.assert_called_once()
        mock_queue.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_unfreeze_updates_message_templates(self, unfreeze_handler, mock_incidents, 
                                                     mock_application, mock_queue):
        """Test that unfreeze calls template form_message methods."""
        incident_uniq_id = 'incident123'

        frozen_until = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="firing",
            frozen_until=frozen_until
        )
        mock_incident.is_frozen = Mock(return_value=True)
        mock_incident.channel_id = "C123456789"
        mock_incident.ts = "1234567890.123456"
        mock_incident.status_update_datetime = datetime.now(timezone.utc)

        mock_incidents.uniq_ids = {incident_uniq_id: mock_incident}

        await unfreeze_handler.handle(incident_uniq_id)

        # Should call form_message on all templates
        assert mock_application.header_template.form_message.call_count >= 2
        assert mock_application.body_template.form_message.call_count >= 1
        assert mock_application.status_icons_template.form_message.call_count >= 1

    @pytest.mark.asyncio
    async def test_unfreeze_chain_enabled_after_unfreeze(self, unfreeze_handler, mock_incidents, 
                                                        mock_application, mock_queue):
        """Test that chain_enabled is True after unfreeze."""
        incident_uniq_id = 'incident123'

        frozen_until = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="firing",
            frozen_until=frozen_until,
            chain_enabled=False  # Frozen incidents have chain_enabled=False
        )
        mock_incident.is_frozen = Mock(return_value=True)
        mock_incident.channel_id = "C123456789"
        mock_incident.ts = "1234567890.123456"
        mock_incident.status_update_datetime = datetime.now(timezone.utc)

        # Simulate unfreeze setting chain_enabled to True
        def unfreeze_side_effect(uniq_id):
            mock_incident.chain_enabled = True
            mock_incident.frozen_until = None

        mock_incidents.unfreeze_incident.side_effect = unfreeze_side_effect
        mock_incidents.uniq_ids = {incident_uniq_id: mock_incident}

        await unfreeze_handler.handle(incident_uniq_id)

        # Should call update_thread with chain_enabled=True
        mock_application.update_thread.assert_called_once()
        call_args = mock_application.update_thread.call_args[0]
        assert call_args[6] is True  # chain_enabled parameter

    @pytest.mark.asyncio
    async def test_unfreeze_multiple_incidents_sequentially(self, unfreeze_handler, mock_incidents, 
                                                           mock_application, mock_queue):
        """Test unfreezing multiple incidents sequentially."""
        frozen_until = datetime.now(timezone.utc) + timedelta(hours=1)

        # Create two frozen incidents
        incident1 = create_mock_incident_for_handlers(
            uuid="test-uuid-1",
            status="firing",
            frozen_until=frozen_until
        )
        incident1.is_frozen = Mock(return_value=True)
        incident1.channel_id = "C123456789"
        incident1.ts = "1234567890.123456"
        incident1.status_update_datetime = datetime.now(timezone.utc)

        incident2 = create_mock_incident_for_handlers(
            uuid="test-uuid-2",
            status="unknown",
            frozen_until=frozen_until
        )
        incident2.is_frozen = Mock(return_value=True)
        incident2.channel_id = "C987654321"
        incident2.ts = "9876543210.654321"
        incident2.status_update_datetime = datetime.now(timezone.utc)

        # Unfreeze first incident
        mock_incidents.uniq_ids = {'incident1': incident1}
        await unfreeze_handler.handle('incident1')

        # Unfreeze second incident
        mock_incidents.uniq_ids = {'incident2': incident2}
        await unfreeze_handler.handle('incident2')

        # Both should have been unfrozen
        assert mock_incidents.unfreeze_incident.call_count == 2
        assert mock_application.post_thread.call_count == 2
        assert mock_application.update_thread.call_count == 2

    @pytest.mark.asyncio
    async def test_inhibition_unfreeze_skips_notification(self, unfreeze_handler, mock_incidents, 
                                                          mock_application, mock_queue):
        """Test that inhibition-based unfreeze skips posting notification."""
        incident_uniq_id = 'incident123'

        # Create incident frozen by inhibition (not time-based)
        mock_incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="firing",
            frozen_until=None,  # No time-based freeze
            frozen_by_inhibition=True  # Frozen by inhibition
        )
        mock_incident.is_frozen = Mock(return_value=True)
        mock_incident.channel_id = "C123456789"
        mock_incident.ts = "1234567890.123456"
        mock_incident.status_update_datetime = datetime.now(timezone.utc)

        mock_incidents.uniq_ids = {incident_uniq_id: mock_incident}

        await unfreeze_handler.handle(incident_uniq_id)

        # Should call unfreeze_incident
        mock_incidents.unfreeze_incident.assert_called_once_with(incident_uniq_id)

        # Should NOT post notification for inhibition unfreeze
        mock_application.post_thread.assert_not_called()

        # Should still update thread and recreate queue
        mock_queue.put_first.assert_called_once()
        mock_queue.recreate.assert_called_once()
        mock_queue.put.assert_called_once()
        mock_application.update_thread.assert_called_once()

    @pytest.mark.asyncio
    async def test_time_based_unfreeze_posts_notification(self, unfreeze_handler, mock_incidents, 
                                                          mock_application, mock_queue):
        """Test that time-based unfreeze posts notification."""
        incident_uniq_id = 'incident123'

        frozen_until = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="firing",
            frozen_until=frozen_until,
            frozen_by_inhibition=False  # Not inhibition-based
        )
        mock_incident.is_frozen = Mock(return_value=True)
        mock_incident.channel_id = "C123456789"
        mock_incident.ts = "1234567890.123456"
        mock_incident.status_update_datetime = datetime.now(timezone.utc)

        mock_incidents.uniq_ids = {incident_uniq_id: mock_incident}

        await unfreeze_handler.handle(incident_uniq_id)

        # Should call unfreeze_incident
        mock_incidents.unfreeze_incident.assert_called_once()

        # Should post notification for time-based unfreeze
        mock_application.post_thread.assert_called_once()

        # Should update thread and recreate queue
        mock_application.update_thread.assert_called_once()

    @pytest.mark.asyncio
    async def test_both_freeze_types_inhibition_takes_precedence(self, unfreeze_handler, mock_incidents, 
                                                                  mock_application, mock_queue):
        """Test that when both freeze types are active, inhibition behavior takes precedence."""
        incident_uniq_id = 'incident123'

        frozen_until = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="firing",
            frozen_until=frozen_until,  # Has time-based freeze
            frozen_by_inhibition=True   # Also has inhibition freeze
        )
        mock_incident.is_frozen = Mock(return_value=True)
        mock_incident.channel_id = "C123456789"
        mock_incident.ts = "1234567890.123456"
        mock_incident.status_update_datetime = datetime.now(timezone.utc)

        mock_incidents.uniq_ids = {incident_uniq_id: mock_incident}

        await unfreeze_handler.handle(incident_uniq_id)

        # Should NOT post notification (inhibition takes precedence)
        mock_application.post_thread.assert_not_called()

        # Should still unfreeze and update
        mock_incidents.unfreeze_incident.assert_called_once()
        mock_application.update_thread.assert_called_once()
