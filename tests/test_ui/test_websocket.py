"""
Unit tests for app.ui.websocket module.
"""
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.config.validation import UIConfig
from app.ui.websocket import AsyncIncidentWS, incident_ws


class TestAsyncIncidentWS:
    """Test cases for AsyncIncidentWS class."""

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
        mock_incidents.get_active_table.return_value = [{'id': '123'}, {'id': '456'}]

        with patch.object(ws, '_get_values', return_value={'field1': 'value1'}), \
                patch.object(ws, 'broadcast', new_callable=AsyncMock) as mock_broadcast:
            await ws.send_full_table(mock_incidents)

            mock_incidents.get_active_table.assert_called_once_with({'field1': 'value1'})
            mock_broadcast.assert_called_once_with('update_data', [{'id': '123'}, {'id': '456'}])

    @pytest.mark.asyncio
    async def test_handle_request_data_success(self):
        """Test handle_request_data method with successful data retrieval."""
        ws = AsyncIncidentWS()
        mock_websocket = AsyncMock()
        mock_incidents = Mock()
        mock_incidents.get_active_table.return_value = [{'id': '123'}, {'id': '456'}]

        with patch.object(ws, '_get_values', return_value={'field1': 'value1'}):
            await ws.handle_request_data(mock_websocket, mock_incidents)

            mock_incidents.get_active_table.assert_called_once_with({'field1': 'value1'})
            expected_message = json.dumps({"event": "update_data", "data": [{'id': '123'}, {'id': '456'}]})
            mock_websocket.send_text.assert_called_once_with(expected_message)

    @pytest.mark.asyncio
    async def test_handle_request_data_exception(self):
        """Test handle_request_data method with exception."""
        ws = AsyncIncidentWS()
        mock_websocket = AsyncMock()
        mock_incidents = Mock()
        mock_incidents.get_active_table.side_effect = Exception("Database error")

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

    @patch('app.ui.table_config.get_config')
    def test_get_values_uses_reloaded_configuration(self, mock_get_config):
        mock_get_config.return_value = Mock(ui_config=None)
        ws = AsyncIncidentWS()
        assert ws._get_values() == {}

        mock_get_config.return_value = Mock(ui_config=UIConfig(columns=[
            {'name': 'status', 'header': 'Status', 'value': 'incident.status', 'visible': False},
            {'name': 'link', 'header': 'Link', 'value': 'incident.uniq_id', 'type': 'link', 'url': 'incident.link'},
        ]))

        assert ws._get_values() == {
            'status': 'incident.status',
            'link': 'incident.uniq_id',
            'linkUrl': 'incident.link',
        }

    @pytest.mark.asyncio
    @patch('app.ui.table_config.get_config')
    async def test_reserved_link_cannot_replace_another_column_value(self, mock_get_config, sample_incident):
        mock_get_config.return_value.ui_config = UIConfig(columns=[
            {'name': '_statusUrl', 'header': 'Status text', 'value': 'incident.status'},
            {'name': '_status', 'header': 'Ignored', 'value': 'incident.uniq_id',
             'type': 'link', 'url': 'incident.config'},
        ])
        ws = AsyncIncidentWS()
        websocket = AsyncMock()
        ws.connections.add(websocket)

        await ws.update_row(sample_incident)

        event = json.loads(websocket.send_text.call_args.args[0])
        assert event['data']['_status'] == sample_incident.status
        assert event['data']['_statusUrl'] == sample_incident.status

    def test_global_incident_ws_instance(self):
        """Test that the global incident_ws instance is created."""
        assert incident_ws is not None
        assert isinstance(incident_ws, AsyncIncidentWS)
