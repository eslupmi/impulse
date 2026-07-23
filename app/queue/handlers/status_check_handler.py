from app.logging import logger
from app.queue.handlers.base_handler import BaseHandler


class StatusCheckHandler(BaseHandler):
    """
    Handler that checks incident status and performs appropriate actions:
    - Removes incident file for 'closed' status
    - Fully deletes incident for 'deleted' status
    - Removes from active map when appropriate
    """

    def __init__(self, queue, application, incidents, inhibition_manager):
        super().__init__(queue, application, incidents)
        self.inhibition_manager = inhibition_manager

    async def handle(self, uniq_id: str):
        incident = self.incidents.uniq_ids.get(uniq_id)
        if incident is None:
            logger.warning("Incident not found", extra={'uniq_id': uniq_id})
            return

        # Skip any actions if incident is frozen
        if incident.is_frozen:
            logger.debug("Incident frozen, skipping actions", extra={'uniq_id': incident.uniq_id})
            return

        if incident.status == 'deleted':
            await self.inhibition_manager.handle_closed(incident)
            logger.debug("Removing incident", extra={'uniq_id': incident.uniq_id})
            self.incidents.del_by_uniq_id(uniq_id)
            return

        # Handle closed status - remove from active map only (file cleanup handled by update_status)
        if incident.status == 'closed':
            logger.info("Incident closed", extra={'uniq_id': incident.uniq_id})
            self.incidents.remove_from_active_map(incident.uuid)
