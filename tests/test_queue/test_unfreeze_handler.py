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
from app.incident.freeze import FreezeSource
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
        app.update_incident_message = AsyncMock()
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
    def mock_maintenance_manager(self):
        """Create mock maintenance manager."""
        manager = Mock()
        manager.reconcile_incident = AsyncMock()
        return manager

    @pytest.fixture
    def unfreeze_handler(self, mock_queue, mock_application, mock_incidents, mock_maintenance_manager):
        """Create UnfreezeHandler instance for testing."""
        return UnfreezeHandler(mock_queue, mock_application, mock_incidents, mock_maintenance_manager)

    @pytest.mark.asyncio
    async def test_handler_initialization(self, mock_queue, mock_application, mock_incidents, mock_maintenance_manager):
        """Test UnfreezeHandler initialization."""
        handler = UnfreezeHandler(mock_queue, mock_application, mock_incidents, mock_maintenance_manager)

        assert handler.queue == mock_queue
        assert handler.app == mock_application
        assert handler.incidents == mock_incidents
        assert handler.maintenance_manager == mock_maintenance_manager

    @pytest.mark.asyncio
    async def test_handle_nonexistent_incident(self, unfreeze_handler, mock_incidents, mock_application):
        """Test handling unfreeze for non-existent incident."""
        incident_uniq_id = 'nonexistent123'
        mock_incidents.uniq_ids = {}

        # Should not raise an error, just return early
        await unfreeze_handler.handle(incident_uniq_id, FreezeSource.TIME.value)

        # Should NOT call any methods
        mock_application.post_thread.assert_not_called()
        mock_application.update_thread.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_removes_time_source_then_reconciles_maintenance(
        self, unfreeze_handler, mock_incidents, mock_maintenance_manager
    ):
        """Scheduled unfreeze clears time source and lets maintenance recalculate parents."""
        incident = create_mock_incident_for_handlers()
        incident.uniq_id = "test-uniq-id"
        incident.frozen_until_source = FreezeSource.TIME.value
        incident.ts = "1.2"
        mock_incidents.uniq_ids = {incident.uniq_id: incident}

        with patch("app.queue.handlers.unfreeze_handler.remove_freeze_source", new_callable=AsyncMock) as remove_source:
            await unfreeze_handler.handle(incident.uniq_id, FreezeSource.TIME.value)

        remove_source.assert_awaited_once_with(
            incident, unfreeze_handler.app, unfreeze_handler.queue, source=FreezeSource.TIME, notify=True
        )
        mock_maintenance_manager.reconcile_incident.assert_awaited_once_with(incident, update_message=False)
        unfreeze_handler.app.update_incident_message.assert_awaited_once_with(incident)

    @pytest.mark.asyncio
    async def test_handle_same_flow_when_inhibition_still_holds(
        self, unfreeze_handler, mock_incidents, mock_maintenance_manager
    ):
        """Inhibition is preserved because only the time source is removed."""
        incident = create_mock_incident_for_handlers(
            frozen_until=datetime.now(timezone.utc) + timedelta(minutes=5),
            frozen_by_inhibition=True,
            frozen_by_maintenance=True,
        )
        incident.uniq_id = "test-uniq-id"
        incident.frozen_until_source = FreezeSource.TIME.value
        mock_incidents.uniq_ids = {incident.uniq_id: incident}

        with patch("app.queue.handlers.unfreeze_handler.remove_freeze_source", new_callable=AsyncMock) as remove_source:
            await unfreeze_handler.handle(incident.uniq_id, FreezeSource.TIME.value)

        remove_source.assert_awaited_once_with(
            incident, unfreeze_handler.app, unfreeze_handler.queue, source=FreezeSource.TIME, notify=True
        )
        mock_maintenance_manager.reconcile_incident.assert_awaited_once_with(incident, update_message=False)
        unfreeze_handler.app.update_incident_message.assert_awaited_once_with(incident)

    @pytest.mark.asyncio
    async def test_handle_ignores_stale_unfreeze_source(
        self, unfreeze_handler, mock_incidents, mock_maintenance_manager
    ):
        """A stale maintenance UNFREEZE must not clear a current manual freeze."""
        incident = create_mock_incident_for_handlers(
            frozen_until=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        incident.uniq_id = "test-uniq-id"
        incident.frozen_until_source = FreezeSource.TIME.value
        mock_incidents.uniq_ids = {incident.uniq_id: incident}

        with patch("app.queue.handlers.unfreeze_handler.remove_freeze_source", new_callable=AsyncMock) as remove_source:
            await unfreeze_handler.handle(incident.uniq_id, FreezeSource.MAINTENANCE.value)

        remove_source.assert_not_called()
        mock_maintenance_manager.reconcile_incident.assert_not_called()
        unfreeze_handler.app.update_incident_message.assert_not_called()

