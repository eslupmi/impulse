"""Handler for updating message content without status changes"""
from app.queue.handlers.base_handler import BaseHandler


class MessageUpdateHandler(BaseHandler):
    """
    MessageUpdateHandler class is responsible for handling simple message updates
    without changing incident status or triggering status-related logic.
    """
    async def handle(self, uniq_id):
        incident = self.incidents.uniq_ids.get(uniq_id)
        
        await self.app.update(
            incident, incident.status, incident.payload,
            False, incident.chain_enabled, incident.frozen_until, incident.task_link
        )

