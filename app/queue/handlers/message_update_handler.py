"""Handler for updating message content without status changes"""
from app.queue.handlers.base_handler import BaseHandler


class MessageUpdateHandler(BaseHandler):
    """
    MessageUpdateHandler class is responsible for handling simple message updates
    without changing incident status or triggering status-related logic.
    """
    async def handle(self, uuid_):
        incident = self.incidents.by_uuid[uuid_]
        
        await self.app.update(
            uuid_, incident, incident.status, incident.payload,
            updated_status=False,
            chain_enabled=incident.chain_enabled,
            status_enabled=incident.status_enabled,
            task_link=incident.task_link
        )

