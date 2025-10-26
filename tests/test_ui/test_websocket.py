"""
Unit tests for app.ui.websocket module.
"""
import json
from unittest.mock import Mock, AsyncMock, patch

import pytest

from app.ui.websocket import AsyncIncidentWS, incident_ws
from tests.utils import create_mock_config


class TestAsyncIncidentWS:
    """Test cases for AsyncIncidentWS class."""

    @patch('app.ui.websocket.get_config')
    def test_async_incident_ws_initialization(self, mock_get_config):
        """Test AsyncIncidentWS initialization."""
        # Use utility function for mock config
        mock_config = create_mock_config()
        mock_ui_config = Mock()
        mock_ui_config.columns = []
        mock_config.ui_config = mock_ui_config
        mock_get_config.return_value = mock_config

        ws = AsyncIncidentWS()

        assert ws.connections == set()
        assert ws.table_config == mock_ui_config

    @pytest.mark.asyncio
    async def test_connect(self):
        """Test WebSocket connection."""
        ws = AsyncIncidentWS()
        mock_websocket = AsyncMock()

        await ws.connect(mock_websocket)

        mock_websocket.accept.assert_called_once()
        assert mock_websocket in ws.connections

    def test_disconnect(self):
        """Test WebSocket disconnection."""
        ws = AsyncIncidentWS()
        mock_websocket = Mock()
        ws.connections.add(mock_websocket)

        ws.disconnect(mock_websocket)

        assert mock_websocket not in ws.connections

    def test_disconnect_nonexistent_websocket(self):
        """Test disconnecting a WebSocket that's not in connections."""
        ws = AsyncIncidentWS()
        mock_websocket = Mock()

        # Should not raise an exception
        ws.disconnect(mock_websocket)

        assert len(ws.connections) == 0

    @pytest.mark.asyncio
    async def test_broadcast_no_connections(self):
        """Test broadcast with no connections."""
        ws = AsyncIncidentWS()

        # Should not raise an exception
        await ws.broadcast('test_event', {'data': 'test'})

    @pytest.mark.asyncio
    async def test_broadcast_success(self):
        """Test successful broadcast to all connections."""
        ws = AsyncIncidentWS()
        mock_websocket1 = AsyncMock()
        mock_websocket2 = AsyncMock()
        ws.connections.add(mock_websocket1)
        ws.connections.add(mock_websocket2)

        await ws.broadcast('test_event', {'data': 'test'})

        expected_message = json.dumps({"event": "test_event", "data": {"data": "test"}})
        mock_websocket1.send_text.assert_called_once_with(expected_message)
        mock_websocket2.send_text.assert_called_once_with(expected_message)

    @pytest.mark.asyncio
    async def test_broadcast_with_disconnected_client(self):
        """Test broadcast with one client failing to receive message."""
        ws = AsyncIncidentWS()
        mock_websocket1 = AsyncMock()
        mock_websocket2 = AsyncMock()
        mock_websocket2.send_text.side_effect = Exception("Connection lost")
        ws.connections.add(mock_websocket1)
        ws.connections.add(mock_websocket2)

        await ws.broadcast('test_event', {'data': 'test'})

        # First websocket should receive the message
        expected_message = json.dumps({"event": "test_event", "data": {"data": "test"}})
        mock_websocket1.send_text.assert_called_once_with(expected_message)

        # Second websocket should be removed from connections
        assert mock_websocket2 not in ws.connections
        assert mock_websocket1 in ws.connections

    @pytest.mark.asyncio
    async def test_update_row(self):
        """Test update_row method."""
        ws = AsyncIncidentWS()
        mock_incident = Mock()
        mock_incident.get_table_data.return_value = {'id': '123', 'status': 'firing'}

        with patch.object(ws, '_get_values', return_value={'field1': 'value1'}), \
                patch.object(ws, 'broadcast', new_callable=AsyncMock) as mock_broadcast:
            await ws.update_row(mock_incident)

            mock_incident.get_table_data.assert_called_once_with({'field1': 'value1'})
            mock_broadcast.assert_called_once_with('update_row', {'id': '123', 'status': 'firing'})

    @pytest.mark.asyncio
    async def test_add_row(self):
        """Test add_row method."""
        ws = AsyncIncidentWS()
        mock_incident = Mock()
        mock_incident.get_table_data.return_value = {'id': '456', 'status': 'resolved'}

        with patch.object(ws, '_get_values', return_value={'field1': 'value1'}), \
                patch.object(ws, 'broadcast', new_callable=AsyncMock) as mock_broadcast:
            await ws.add_row(mock_incident)

            mock_incident.get_table_data.assert_called_once_with({'field1': 'value1'})
            mock_broadcast.assert_called_once_with('add_row', {'id': '456', 'status': 'resolved'})

    @pytest.mark.asyncio
    async def test_remove_row(self):
        """Test remove_row method."""
        ws = AsyncIncidentWS()
        mock_incident = Mock()
        mock_incident.get_table_data.return_value = {'id': '789', 'status': 'unknown'}

        with patch.object(ws, '_get_values', return_value={'field1': 'value1'}), \
                patch.object(ws, 'broadcast', new_callable=AsyncMock) as mock_broadcast:
            await ws.remove_row(mock_incident)

            mock_incident.get_table_data.assert_called_once_with({'field1': 'value1'})
            mock_broadcast.assert_called_once_with('remove_row', {'id': '789', 'status': 'unknown'})

    @pytest.mark.asyncio
    async def test_send_full_table(self):
        """Test send_full_table method."""
        ws = AsyncIncidentWS()
        mock_incidents = Mock()
        mock_incidents.get_table.return_value = [{'id': '123'}, {'id': '456'}]

        with patch.object(ws, '_get_values', return_value={'field1': 'value1'}), \
                patch.object(ws, 'broadcast', new_callable=AsyncMock) as mock_broadcast:
            await ws.send_full_table(mock_incidents)

            mock_incidents.get_table.assert_called_once_with({'field1': 'value1'})
            mock_broadcast.assert_called_once_with('update_data', [{'id': '123'}, {'id': '456'}])

    @pytest.mark.asyncio
    async def test_handle_request_data_success(self):
        """Test handle_request_data method with successful data retrieval."""
        ws = AsyncIncidentWS()
        mock_websocket = AsyncMock()
        mock_incidents = Mock()
        mock_incidents.get_table.return_value = [{'id': '123'}, {'id': '456'}]

        with patch.object(ws, '_get_values', return_value={'field1': 'value1'}):
            await ws.handle_request_data(mock_websocket, mock_incidents)

            mock_incidents.get_table.assert_called_once_with({'field1': 'value1'})
            expected_message = json.dumps({"event": "update_data", "data": [{'id': '123'}, {'id': '456'}]})
            mock_websocket.send_text.assert_called_once_with(expected_message)

    @pytest.mark.asyncio
    async def test_handle_request_data_exception(self):
        """Test handle_request_data method with exception."""
        ws = AsyncIncidentWS()
        mock_websocket = AsyncMock()
        mock_incidents = Mock()
        mock_incidents.get_table.side_effect = Exception("Database error")

        with patch.object(ws, '_get_values', return_value={'field1': 'value1'}), \
                patch('app.ui.websocket.logger') as mock_logger:
            await ws.handle_request_data(mock_websocket, mock_incidents)

            mock_logger.error.assert_called_once()
            mock_websocket.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_ping(self):
        """Test handle_ping method."""
        ws = AsyncIncidentWS()
        mock_websocket = AsyncMock()

        await ws.handle_ping(mock_websocket)

        expected_message = json.dumps({"event": "pong"})
        mock_websocket.send_text.assert_called_once_with(expected_message)

    def test_get_values_with_regular_fields(self):
        """Test _get_values method with regular fields."""
        ws = AsyncIncidentWS()

        # Mock table config with regular fields
        mock_field1 = Mock()
        mock_field1.name = 'status'
        mock_field1.type = 'string'
        mock_field1.value = 'firing'

        mock_field2 = Mock()
        mock_field2.name = 'severity'
        mock_field2.type = 'string'
        mock_field2.value = 'critical'

        ws.table_config.columns = [mock_field1, mock_field2]

        result = ws._get_values()

        expected = {
            'status': 'firing',
            'severity': 'critical'
        }
        assert result == expected

    def test_get_values_with_link_fields(self):
        """Test _get_values method with link fields."""
        ws = AsyncIncidentWS()

        # Mock table config with link field
        mock_field1 = Mock()
        mock_field1.name = 'status'
        mock_field1.type = 'string'
        mock_field1.value = 'firing'

        mock_field2 = Mock()
        mock_field2.name = 'link'
        mock_field2.type = 'link'
        mock_field2.value = 'Incident Link'
        mock_field2.url = 'https://example.com/incident/123'

        ws.table_config.columns = [mock_field1, mock_field2]

        result = ws._get_values()

        expected = {
            'status': 'firing',
            'link': 'Incident Link',
            'linkUrl': 'https://example.com/incident/123'
        }
        assert result == expected

    def test_get_values_mixed_fields(self):
        """Test _get_values method with mixed field types."""
        ws = AsyncIncidentWS()

        # Mock table config with mixed fields
        mock_field1 = Mock()
        mock_field1.name = 'status'
        mock_field1.type = 'string'
        mock_field1.value = 'firing'

        mock_field2 = Mock()
        mock_field2.name = 'link'
        mock_field2.type = 'link'
        mock_field2.value = 'Incident Link'
        mock_field2.url = 'https://example.com/incident/123'

        mock_field3 = Mock()
        mock_field3.name = 'severity'
        mock_field3.type = 'string'
        mock_field3.value = 'critical'

        ws.table_config.columns = [mock_field1, mock_field2, mock_field3]

        result = ws._get_values()

        expected = {
            'status': 'firing',
            'link': 'Incident Link',
            'linkUrl': 'https://example.com/incident/123',
            'severity': 'critical'
        }
        assert result == expected

    def test_global_incident_ws_instance(self):
        """Test that the global incident_ws instance is created."""
        assert incident_ws is not None
        assert isinstance(incident_ws, AsyncIncidentWS)
