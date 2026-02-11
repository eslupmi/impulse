from app.incident.unfreeze import unfreeze_incident
from app.logging import logger
from app.queue.handlers.base_handler import BaseHandler


class UnfreezeHandler(BaseHandler):
    """
    Handle unfreeze events when freeze duration expires.
    Delegates status-based cleanup to StatusCheckHandler.
    """
    __slots__ = []

    async def handle(self, uniq_id: str):
        """
        Handle unfreeze for an incident
        
        :param uniq_id: Incident unique ID
        """
        incident = self.incidents.uniq_ids.get(uniq_id)
        if incident is None:
            logger.warning(f'Incident with uniq_id {uniq_id} not found for unfreeze')
            return

        await unfreeze_incident(incident, self.app, self.queue)
        await self.app.update_thread(incident)
