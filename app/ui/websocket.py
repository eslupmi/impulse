import json
from typing import Set

from fastapi import WebSocket

from app.config.config import get_config
from app.logging import logger


class AsyncIncidentWS:
    """Async WebSocket manager for incident updates"""
    
    def __init__(self):
        self.connections: Set[WebSocket] = set()
        self.table_config = get_config().ui_config

    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.connections.add(websocket)
        logger.debug(f"WebSocket connected. Total connections: {len(self.connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        self.connections.discard(websocket)
        logger.debug(f"WebSocket disconnected. Total connections: {len(self.connections)}")

    async def broadcast(self, event: str, data: dict):
        """Broadcast a message to all connected clients"""
        if not self.connections:
            return

        message = json.dumps({"event": event, "data": data})
        disconnected = set()

        for websocket in self.connections:
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.warning(f"Failed to send message to WebSocket: {e}")
                disconnected.add(websocket)

        # Remove disconnected clients
        for websocket in disconnected:
            self.connections.discard(websocket)

    async def update_row(self, incident):
        """Send row update to all connected clients"""
        row_data = incident.get_table_data(self._get_values())
        await self.broadcast('update_row', row_data)

    async def add_row(self, incident):
        """Send new row to all connected clients"""
        row_data = incident.get_table_data(self._get_values())
        await self.broadcast('add_row', row_data)

    async def remove_row(self, incident):
        """Send row removal to all connected clients"""
        row_data = incident.get_table_data(self._get_values())
        await self.broadcast('remove_row', row_data)

    async def send_full_table(self, incidents):
        """Send full table data to all connected clients"""
        data = incidents.get_active_table(self._get_values())
        await self.broadcast('update_data', data)

    async def handle_request_data(self, websocket: WebSocket, incidents, show_full_table: bool = False):
        """Handle request_data event from a specific client"""
        try:
            if show_full_table:
                data = incidents.get_full_table(self._get_values())
            else:
                data = incidents.get_active_table(self._get_values())
            message = json.dumps({"event": "update_data", "data": data})
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Failed to send full table data: {e}")

    @staticmethod
    async def handle_ping(websocket: WebSocket):
        """Handle ping event from a specific client"""
        await websocket.send_text(json.dumps({"event": "pong"}))

    def _get_values(self):
        """Get values mapping for table configuration"""
        values_map = {}
        if self.table_config is None or not self.table_config.columns:
            return values_map
        
        for field in self.table_config.columns:
            if field.type == 'link':
                values_map[field.name] = field.value
                values_map[f'{field.name}Url'] = field.url
            else:
                values_map[field.name] = field.value
        return values_map


# Global instance
incident_ws = AsyncIncidentWS()
