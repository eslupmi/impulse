from datetime import datetime, timezone
from typing import Callable, List, Optional, TYPE_CHECKING

from app.logging import logger
from app.maintenance.models import MaintenanceWindow
from app.maintenance.store import MaintenanceStore
from app.queue.constants import QueueItemType
from app.incident.freeze import FreezeSource, MAINTENANCE_PARENT_SENTINEL
from app.incident.incident import remove_freeze_source

if TYPE_CHECKING:
    from app.incident.incident import Incident
    from app.incident.incidents import Incidents
    from app.im.application import Application
    from app.queue.queue import AsyncQueue


class MaintenanceManager:
    """Evaluates maintenance windows and applies time-based freeze to matching incidents.

    Co-equal with InhibitionManager: an incident event must be checked against both.
    Maintenance records its source in incident.parents. Effective freeze state is recalculated
    centrally from parents plus frozen_until.
    Maintenance has higher display priority (frozen_by_maintenance) when both apply.
    """

    __slots__ = ["store", "incidents", "application", "queue", "_now"]

    def __init__(
        self,
        store: MaintenanceStore,
        incidents: "Incidents",
        application: "Application",
        queue: "AsyncQueue",
        now: Optional[Callable[[], datetime]] = None,
    ):
        self.store = store
        self.incidents = incidents
        self.application = application
        self.queue = queue
        self._now = now or (lambda: datetime.now(timezone.utc))

    def _active_sorted(self, now: Optional[datetime] = None) -> List[MaintenanceWindow]:
        now = now or self._now()
        active = [w for w in self.store.list() if w.is_active(now)]
        active.sort(key=lambda w: (w.starts_at, w.ends_at, w.id))
        return active

    def _first_matching_window(
        self, incident: "Incident", require_future_end: bool = False
    ) -> Optional[MaintenanceWindow]:
        now = self._now()
        for window in self._active_sorted(now):
            if require_future_end and window.ends_at <= now:
                continue
            if window.matches_incident(incident):
                return window
        return None

    def would_match_active_window(self, incident: "Incident") -> bool:
        return self._first_matching_window(incident) is not None

    async def process_incident(self, incident: "Incident"):
        window = self._first_matching_window(incident)
        if window is None:
            return

        was_frozen = incident.is_frozen()
        incident.set_maintenance_parent()

        if was_frozen:
            logger.info(
                "Maintenance source recorded on frozen incident",
                extra={"uuid": incident.uuid, "window_id": window.id, "until": window.ends_at},
            )
            return

        await self.application.apply_time_freeze(incident, window.ends_at, user=None, queue_=self.queue)
        logger.info(
            "Maintenance time freeze applied",
            extra={"uuid": incident.uuid, "window_id": window.id, "until": window.ends_at},
        )

    async def reconcile_incident(self, incident: "Incident", update_message: bool = True):
        """Recalculate this incident's maintenance source and time-freeze schedule."""
        window = self._first_matching_window(incident, require_future_end=True)
        if window is None:
            await remove_freeze_source(
                incident, self.application, self.queue, source=FreezeSource.MAINTENANCE, notify=False
            )
            if update_message and incident.ts:
                await self.application.update_incident_message(incident)
            return

        had_maintenance = incident.frozen_by_maintenance or MAINTENANCE_PARENT_SENTINEL in incident.parents
        was_frozen = incident.is_frozen()
        incident.set_maintenance_parent()
        if not was_frozen or had_maintenance:
            incident.frozen_until = window.ends_at
            incident.chain_enabled = False
            incident.dump()

            await self.queue.delete_by_id_and_type(incident.uniq_id, QueueItemType.UNFREEZE)
            await self.queue.put(window.ends_at, QueueItemType.UNFREEZE, incident.uniq_id)

            logger.info(
                "Maintenance time freeze scheduled",
                extra={"uuid": incident.uuid, "window_id": window.id, "until": window.ends_at},
            )

        if update_message and incident.ts:
            await self.application.update_incident_message(incident)

    async def reconcile_after_window_removed(self, removed_window: MaintenanceWindow):
        for uniq_id in list(self.incidents.uniq_ids.keys()):
            incident = self.incidents.uniq_ids.get(uniq_id)
            if incident is None or incident.status in ("closed", "deleted"):
                continue
            if not removed_window.matches_incident(incident):
                continue
            await self.reconcile_incident(incident)

    async def reconcile_on_startup(self):
        for uniq_id in list(self.incidents.uniq_ids.keys()):
            incident = self.incidents.uniq_ids.get(uniq_id)
            if incident is None or incident.status in ("closed", "deleted"):
                continue
            if self.would_match_active_window(incident):
                await self.reconcile_incident(incident)
            elif MAINTENANCE_PARENT_SENTINEL in incident.parents or incident.frozen_by_maintenance:
                await self.reconcile_incident(incident)

    async def reconcile_active_incidents(self):
        await self.reconcile_on_startup()
