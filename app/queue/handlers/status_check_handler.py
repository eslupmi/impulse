from app.logging import logger
from app.queue.handlers.base_handler import BaseHandler


class StatusCheckHandler(BaseHandler):
    """
    Handler that checks incident status and performs appropriate actions:
    - Removes incident file for 'closed' status
    - Fully deletes incident for 'deleted' status
    - Removes from active map when appropriate
    """

    async def handle(self, uniq_id: str):
        """
        Check incident status and perform appropriate actions
        
        Args:
            uniq_id: The unique identifier of the incident to check
        """
        incident = self.incidents.uniq_ids.get(uniq_id)
        if incident is None:
            logger.warning("Incident not found", extra={'extra_fields': {'uniq_id': uniq_id}})
            return

        # Skip any actions if incident is frozen
        if incident.is_frozen():
            logger.debug("Incident frozen, skipping actions", extra={'extra_fields': {'uuid': incident.uuid}})
            return

        # Handle deleted status - full deletion
        if incident.status == 'deleted':
            logger.debug("Removing incident", extra={'extra_fields': {'uuid': incident.uuid}})
            self.incidents.del_by_uniq_id(uniq_id)
            return

        # Handle closed status - remove from active map only (file cleanup handled by update_status)
        if incident.status == 'closed':
            logger.info("Incident closed", extra={'extra_fields': {'uuid': incident.uuid}})
            self.incidents.remove_from_active_map(incident.uuid)
