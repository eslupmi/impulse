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
        incidents.by_uuid = {}
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
        incident.status = "firing"
        incident.payload = {"test": "data"}
        incident.chain_enabled = True
        incident.status_enabled = True
        incident.task_link = "https://jira.com/browse/DTS-123"
        return incident

    @pytest.mark.asyncio
    async def test_handle_updates_message_without_status_change(self, handler, mock_incident):
        """Test that handler updates message without changing status"""
        handler.incidents.by_uuid[mock_incident.uuid] = mock_incident

        await handler.handle(mock_incident.uuid)

        handler.app.update.assert_called_once_with(
            mock_incident.uuid,
            mock_incident,
            mock_incident.status,
            mock_incident.payload,
            updated_status=False,
            chain_enabled=mock_incident.chain_enabled,
            status_enabled=mock_incident.status_enabled,
            task_link=mock_incident.task_link
        )

    @pytest.mark.asyncio
    async def test_handle_with_task_link(self, handler, mock_incident):
        """Test handler with task link present"""
        mock_incident.task_link = "https://jira.com/browse/DTS-456"
        handler.incidents.by_uuid[mock_incident.uuid] = mock_incident

        await handler.handle(mock_incident.uuid)

        # Verify task_link is passed through correctly
        call_kwargs = handler.app.update.call_args[1]
        assert call_kwargs['task_link'] == "https://jira.com/browse/DTS-456"

    @pytest.mark.asyncio
    async def test_handle_without_task_link(self, handler, mock_incident):
        """Test handler without task link"""
        mock_incident.task_link = ""
        handler.incidents.by_uuid[mock_incident.uuid] = mock_incident

        await handler.handle(mock_incident.uuid)

        # Verify empty task_link is passed through
        call_kwargs = handler.app.update.call_args[1]
        assert call_kwargs['task_link'] == ""

    @pytest.mark.asyncio
    async def test_handle_preserves_incident_state(self, handler, mock_incident):
        """Test that handler preserves all incident state"""
        handler.incidents.by_uuid[mock_incident.uuid] = mock_incident
        
        original_status = mock_incident.status
        original_chain_enabled = mock_incident.chain_enabled
        original_status_enabled = mock_incident.status_enabled

        await handler.handle(mock_incident.uuid)

        # Verify incident state is preserved (not modified by handler)
        call_args = handler.app.update.call_args
        assert call_args[0][2] == original_status  # status
        assert call_args[1]['chain_enabled'] == original_chain_enabled
        assert call_args[1]['status_enabled'] == original_status_enabled

