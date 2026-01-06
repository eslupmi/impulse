from datetime import datetime, timezone

from app.logging import logger
from app.queue.constants import QueueItemType
from app.queue.handlers.base_handler import BaseHandler


class StatusUpdateHandler(BaseHandler):
    """
    StatusUpdateHandler class is responsible for handling the status update event.
    Does NOT handle deletion or file removal - that's delegated to StatusCheckHandler.
    """
    async def handle(self, uniq_id):
        incident = self.incidents.uniq_ids.get(uniq_id)
        if incident is None:
            return
            
        new_status = incident.next_status[incident.status]
        status_updated = incident.update_status(new_status)

        if status_updated:
            logger.info("Status updated", extra={'uuid': incident.uuid, 'status': new_status})

        if incident.status != 'deleted':
            await self.app.update(
                incident, incident.status, incident.payload,
                status_updated, incident.chain_enabled, incident.frozen_until, incident.task_link
            )

        if incident.status == 'unknown' or incident.status == 'closed':
            await self.queue.update(uniq_id, incident.status_update_datetime, incident.status)

        if incident.status == 'closed':
            await self.queue.delete_by_id(uniq_id, delete_steps=True, delete_status=False)
        
        await self.queue.put_first(datetime.now(timezone.utc), QueueItemType.STATUS_CHECK, uniq_id)
