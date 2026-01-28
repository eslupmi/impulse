"""
Unit tests for StatusCheckHandler.

This module tests the StatusCheckHandler which checks incident status and performs
appropriate cleanup actions based on the incident's current state.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock

import pytest

from app.queue.handlers.status_check_handler import StatusCheckHandler
from tests.utils import (
    create_mock_queue,
    create_mock_application,
    create_mock_incidents_collection,
    create_mock_incident_for_handlers
)


class TestStatusCheckHandler:
    """Test cases for StatusCheckHandler class."""

    @pytest.fixture
    def mock_queue(self):
        """Create mock queue."""
        return create_mock_queue()

    @pytest.fixture
    def mock_application(self):
        """Create mock application."""
        return create_mock_application()

    @pytest.fixture
    def mock_incidents(self):
        """Create mock incidents collection."""
        return create_mock_incidents_collection()

    @pytest.fixture
    def mock_inhibition_manager(self):
        """Create mock inhibition manager."""
        manager = Mock()
        manager.process_incident = AsyncMock()
        manager.handle_resolved = AsyncMock()
        manager.handle_closed = AsyncMock()
        return manager

    @pytest.fixture
    def status_check_handler(self, mock_queue, mock_application, mock_incidents, mock_inhibition_manager):
        """Create StatusCheckHandler instance for testing."""
        return StatusCheckHandler(mock_queue, mock_application, mock_incidents, mock_inhibition_manager)

    @pytest.mark.asyncio
    async def test_handler_initialization(self, mock_queue, mock_application, mock_incidents, mock_inhibition_manager):
        """Test StatusCheckHandler initialization."""
        handler = StatusCheckHandler(mock_queue, mock_application, mock_incidents, mock_inhibition_manager)

        assert handler.queue == mock_queue
        assert handler.app == mock_application
        assert handler.incidents == mock_incidents

    @pytest.mark.asyncio
    async def test_handle_deleted_incident(self, status_check_handler, mock_incidents):
        """Test handling incident with 'deleted' status."""
        incident_uniq_id = 'incident123'

        # Create mock incident with deleted status
        mock_incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="deleted",
            frozen_until=None
        )
        mock_incident.is_frozen = Mock(return_value=False)

        mock_incidents.uniq_ids = {incident_uniq_id: mock_incident}
        mock_incidents.del_by_uniq_id = Mock()

        await status_check_handler.handle(incident_uniq_id)

        # Should call del_by_uniq_id to fully delete the incident
        mock_incidents.del_by_uniq_id.assert_called_once_with(incident_uniq_id)

    @pytest.mark.asyncio
    async def test_handle_closed_incident(self, status_check_handler, mock_incidents):
        """Test handling incident with 'closed' status."""
        incident_uniq_id = 'incident123'

        # Create mock incident with closed status
        mock_incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="closed",
            frozen_until=None
        )
        mock_incident.is_frozen = Mock(return_value=False)

        mock_incidents.uniq_ids = {incident_uniq_id: mock_incident}
        mock_incidents.remove_from_active_map = Mock()

        await status_check_handler.handle(incident_uniq_id)

        # Should remove from active map
        mock_incidents.remove_from_active_map.assert_called_once_with(mock_incident.uuid)
        # Should NOT delete the incident completely
        assert not hasattr(mock_incidents, 'del_by_uniq_id') or not mock_incidents.del_by_uniq_id.called

    @pytest.mark.asyncio
    async def test_handle_frozen_incident_skips_actions(self, status_check_handler, mock_incidents):
        """Test that frozen incidents are skipped."""
        incident_uniq_id = 'incident123'

        # Create mock frozen incident with deleted status
        frozen_until = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="deleted",
            frozen_until=frozen_until
        )
        mock_incident.is_frozen = Mock(return_value=True)

        mock_incidents.uniq_ids = {incident_uniq_id: mock_incident}
        mock_incidents.del_by_uniq_id = Mock()
        mock_incidents.remove_from_active_map = Mock()

        await status_check_handler.handle(incident_uniq_id)

        # Should NOT perform any actions on frozen incident
        mock_incidents.del_by_uniq_id.assert_not_called()
        mock_incidents.remove_from_active_map.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_frozen_closed_incident(self, status_check_handler, mock_incidents):
        """Test that frozen closed incidents are skipped."""
        incident_uniq_id = 'incident123'

        # Create mock frozen incident with closed status
        frozen_until = datetime.now(timezone.utc) + timedelta(hours=2)
        mock_incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="closed",
            frozen_until=frozen_until
        )
        mock_incident.is_frozen = Mock(return_value=True)

        mock_incidents.uniq_ids = {incident_uniq_id: mock_incident}
        mock_incidents.remove_from_active_map = Mock()

        await status_check_handler.handle(incident_uniq_id)

        # Should NOT remove from active map since it's frozen
        mock_incidents.remove_from_active_map.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_nonexistent_incident(self, status_check_handler, mock_incidents):
        """Test handling status check for non-existent incident."""
        incident_uniq_id = 'nonexistent123'
        mock_incidents.uniq_ids = {}

        # Should not raise an error, just return early
        await status_check_handler.handle(incident_uniq_id)

    @pytest.mark.asyncio
    async def test_handle_firing_incident_no_action(self, status_check_handler, mock_incidents):
        """Test that firing incidents don't trigger any actions."""
        incident_uniq_id = 'incident123'

        # Create mock incident with firing status
        mock_incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="firing",
            frozen_until=None
        )
        mock_incident.is_frozen = Mock(return_value=False)

        mock_incidents.uniq_ids = {incident_uniq_id: mock_incident}
        mock_incidents.del_by_uniq_id = Mock()
        mock_incidents.remove_from_active_map = Mock()

        await status_check_handler.handle(incident_uniq_id)

        # Should NOT perform any actions on firing incident
        mock_incidents.del_by_uniq_id.assert_not_called()
        mock_incidents.remove_from_active_map.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_unknown_incident_no_action(self, status_check_handler, mock_incidents):
        """Test that unknown incidents don't trigger any actions."""
        incident_uniq_id = 'incident123'

        # Create mock incident with unknown status
        mock_incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="unknown",
            frozen_until=None
        )
        mock_incident.is_frozen = Mock(return_value=False)

        mock_incidents.uniq_ids = {incident_uniq_id: mock_incident}
        mock_incidents.del_by_uniq_id = Mock()
        mock_incidents.remove_from_active_map = Mock()

        await status_check_handler.handle(incident_uniq_id)

        # Should NOT perform any actions on unknown incident
        mock_incidents.del_by_uniq_id.assert_not_called()
        mock_incidents.remove_from_active_map.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_resolved_incident_no_action(self, status_check_handler, mock_incidents):
        """Test that resolved incidents don't trigger any actions."""
        incident_uniq_id = 'incident123'

        # Create mock incident with resolved status
        mock_incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="resolved",
            frozen_until=None
        )
        mock_incident.is_frozen = Mock(return_value=False)

        mock_incidents.uniq_ids = {incident_uniq_id: mock_incident}
        mock_incidents.del_by_uniq_id = Mock()
        mock_incidents.remove_from_active_map = Mock()

        await status_check_handler.handle(incident_uniq_id)

        # Should NOT perform any actions on resolved incident
        mock_incidents.del_by_uniq_id.assert_not_called()
        mock_incidents.remove_from_active_map.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_multiple_deleted_incidents(self, status_check_handler, mock_incidents):
        """Test handling multiple deleted incidents sequentially."""
        # Create two deleted incidents
        incident1 = create_mock_incident_for_handlers(
            uuid="test-uuid-1",
            status="deleted",
            frozen_until=None
        )
        incident1.is_frozen = Mock(return_value=False)

        incident2 = create_mock_incident_for_handlers(
            uuid="test-uuid-2",
            status="deleted",
            frozen_until=None
        )
        incident2.is_frozen = Mock(return_value=False)

        mock_incidents.del_by_uniq_id = Mock()

        # Handle first incident
        mock_incidents.uniq_ids = {'incident1': incident1}
        await status_check_handler.handle('incident1')

        # Handle second incident
        mock_incidents.uniq_ids = {'incident2': incident2}
        await status_check_handler.handle('incident2')

        # Both should have been deleted
        assert mock_incidents.del_by_uniq_id.call_count == 2

    @pytest.mark.asyncio
    async def test_handle_multiple_closed_incidents(self, status_check_handler, mock_incidents):
        """Test handling multiple closed incidents sequentially."""
        # Create two closed incidents
        incident1 = create_mock_incident_for_handlers(
            uuid="test-uuid-1",
            status="closed",
            frozen_until=None
        )
        incident1.is_frozen = Mock(return_value=False)

        incident2 = create_mock_incident_for_handlers(
            uuid="test-uuid-2",
            status="closed",
            frozen_until=None
        )
        incident2.is_frozen = Mock(return_value=False)

        mock_incidents.remove_from_active_map = Mock()

        # Handle first incident
        mock_incidents.uniq_ids = {'incident1': incident1}
        await status_check_handler.handle('incident1')

        # Handle second incident
        mock_incidents.uniq_ids = {'incident2': incident2}
        await status_check_handler.handle('incident2')

        # Both should have been removed from active map
        assert mock_incidents.remove_from_active_map.call_count == 2

    @pytest.mark.asyncio
    async def test_frozen_incident_different_statuses(self, status_check_handler, mock_incidents):
        """Test that frozen incidents with various statuses are all skipped."""
        frozen_until = datetime.now(timezone.utc) + timedelta(hours=1)

        for status in ['firing', 'unknown', 'resolved', 'closed', 'deleted']:
            incident = create_mock_incident_for_handlers(
                uuid=f"test-uuid-{status}",
                status=status,
                frozen_until=frozen_until
            )
            incident.is_frozen = Mock(return_value=True)

            mock_incidents.uniq_ids = {f'incident_{status}': incident}
            mock_incidents.del_by_uniq_id = Mock()
            mock_incidents.remove_from_active_map = Mock()

            await status_check_handler.handle(f'incident_{status}')

            # No actions should be performed for frozen incidents
            mock_incidents.del_by_uniq_id.assert_not_called()
            mock_incidents.remove_from_active_map.assert_not_called()
