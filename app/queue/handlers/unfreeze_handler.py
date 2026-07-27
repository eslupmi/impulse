import asyncio
from typing import TYPE_CHECKING

from app.incident.freeze import FreezeSource
from app.incident.incident import remove_freeze_source
from app.logging import logger
from app.queue.handlers.base_handler import BaseHandler

if TYPE_CHECKING:
    from app.maintenance.manager import MaintenanceManager


class UnfreezeHandler(BaseHandler):
    """
    Handle unfreeze events when freeze duration expires.
    Delegates status-based cleanup to StatusCheckHandler.
    """
    __slots__ = ['maintenance_manager']

    def __init__(self, queue, application, incidents, maintenance_manager: 'MaintenanceManager'):
        super().__init__(queue, application, incidents)
        self.maintenance_manager = maintenance_manager

    async def handle(self, uniq_id: str, source: str):
        """
        Handle unfreeze for an incident

        :param uniq_id: Incident unique ID
        """
        incident = self.incidents.uniq_ids.get(uniq_id)
        if incident is None:
            logger.warning(f'Incident with uniq_id {uniq_id} not found for unfreeze')
            return

        freeze_source = FreezeSource(source)
        if freeze_source == FreezeSource.MAINTENANCE:
            source_active = incident.frozen_by_maintenance
        else:
            source_active = incident.frozen_until_source == freeze_source.value
        if not source_active:
            logger.info(
                "Ignoring stale unfreeze event",
                extra={
                    'uniq_id': incident.uniq_id,
                    'event_source': freeze_source.value,
                    'active_source': incident.frozen_until_source,
                },
            )
            return

        await remove_freeze_source(incident, self.queue, source=freeze_source)
        await self.maintenance_manager.reconcile_incident(incident, update_message=False)
        if freeze_source == FreezeSource.TIME and not incident.is_frozen:
            self.app.track_async_task(
                asyncio.create_task(self.app.post_unfreeze_notification(incident))
            )
        await self.app.update_incident_message(incident)
