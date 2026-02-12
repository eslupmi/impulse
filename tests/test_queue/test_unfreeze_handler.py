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
    async def test_handle_nonexistent_incident(self, unfreeze_handler, mock_incidents, mock_application):
        """Test handling unfreeze for non-existent incident."""
        incident_uniq_id = 'nonexistent123'
        mock_incidents.uniq_ids = {}

        # Should not raise an error, just return early
        await unfreeze_handler.handle(incident_uniq_id)

        # Should NOT call any methods
        mock_application.post_thread.assert_not_called()
        mock_application.update_thread.assert_not_called()

