"""Unit tests for MessageUpdateHandler"""
import pytest
from unittest.mock import Mock, AsyncMock

from app.queue.handlers.message_update_handler import MessageUpdateHandler


class TestMessageUpdateHandler:
    """Test cases for MessageUpdateHandler"""

    @pytest.fixture
    def mock_queue(self):
        """Create mock queue"""
        return Mock()

    @pytest.fixture
    def mock_app(self):
        """Create mock application"""
        app = Mock()
        app.update = AsyncMock()
        return app

    @pytest.fixture
    def mock_incidents(self):
        """Create mock incidents collection"""
        incidents = Mock()
        incidents.uniq_ids = {}
        return incidents

    @pytest.fixture
    def handler(self, mock_queue, mock_app, mock_incidents):
        """Create MessageUpdateHandler instance"""
        return MessageUpdateHandler(mock_queue, mock_app, mock_incidents)

    @pytest.fixture
    def mock_incident(self):
        """Create mock incident"""
        incident = Mock()
        incident.uuid = "test-uuid-123"
        incident.uniq_id = "test-uniq-id-123"
        incident.status = "firing"
        incident.payload = {"test": "data"}
        incident.chain_enabled = True
        incident.status_enabled = True
        incident.task_link = "https://jira.com/browse/DTS-123"
        incident.task_creation_in_progress = False
        return incident

    @pytest.mark.asyncio
    async def test_handle_updates_message_without_status_change(self, handler, mock_incident):
        """Test that handler updates message without changing status"""
        handler.incidents.uniq_ids[mock_incident.uniq_id] = mock_incident

        await handler.handle(mock_incident.uniq_id)

        handler.app.update.assert_called_once_with(
            mock_incident,
            mock_incident.status,
            mock_incident.payload,
            False,
            mock_incident.chain_enabled,
            mock_incident.status_enabled,
            mock_incident.task_link
        )

    @pytest.mark.asyncio
    async def test_handle_with_task_link(self, handler, mock_incident):
        """Test handler with task link present"""
        mock_incident.task_link = "https://jira.com/browse/DTS-456"
        handler.incidents.uniq_ids[mock_incident.uniq_id] = mock_incident

        await handler.handle(mock_incident.uniq_id)

        # Verify task_link is passed through correctly
        call_args = handler.app.update.call_args[0]
        assert call_args[6] == "https://jira.com/browse/DTS-456"

    @pytest.mark.asyncio
    async def test_handle_without_task_link(self, handler, mock_incident):
        """Test handler without task link"""
        mock_incident.task_link = ""
        handler.incidents.uniq_ids[mock_incident.uniq_id] = mock_incident

        await handler.handle(mock_incident.uniq_id)

        # Verify empty task_link is passed through
        call_args = handler.app.update.call_args[0]
        assert call_args[6] == ""

    @pytest.mark.asyncio
    async def test_handle_preserves_incident_state(self, handler, mock_incident):
        """Test that handler preserves all incident state"""
        handler.incidents.uniq_ids[mock_incident.uniq_id] = mock_incident
        
        original_status = mock_incident.status
        original_chain_enabled = mock_incident.chain_enabled
        original_status_enabled = mock_incident.status_enabled

        await handler.handle(mock_incident.uniq_id)

        # Verify incident state is preserved (not modified by handler)
        call_args = handler.app.update.call_args[0]
        assert call_args[1] == original_status  # status
        assert call_args[4] == original_chain_enabled
        assert call_args[5] == original_status_enabled

