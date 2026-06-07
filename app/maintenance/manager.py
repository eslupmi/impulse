from datetime import datetime, timezone
from typing import Callable, List, Optional, TYPE_CHECKING

from app.logging import logger
from app.maintenance.constants import MAINTENANCE_PARENT_SENTINEL
from app.maintenance.models import MaintenanceWindow
from app.maintenance.store import MaintenanceStore

if TYPE_CHECKING:
    from app.incident.incident import Incident
    from app.incident.incidents import Incidents
    from app.im.application import Application
    from app.queue.queue import AsyncQueue


class MaintenanceManager:
    """Evaluates maintenance windows and applies time-based freeze to matching incidents.

    Co-equal with InhibitionManager: an incident event must be checked against both.
    When inhibition is already holding the incident, the maintenance time freeze is deferred
    until inhibition releases it (see try_apply_time_freeze_if_window_still_active).
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

    def _active_sorted(self) -> List[MaintenanceWindow]:
        now = self._now()
        active = [w for w in self.store.list() if w.is_active(now)]
        active.sort(key=lambda w: (w.starts_at, w.ends_at, w.id))
        return active

    def _first_matching_window(self, incident: "Incident") -> Optional[MaintenanceWindow]:
        for window in self._active_sorted():
            if window.matches_incident(incident):
                return window
        return None

    def would_match_active_window(self, incident: "Incident") -> bool:
        return self._first_matching_window(incident) is not None

    async def process_incident(self, incident: "Incident"):
        window = self._first_matching_window(incident)
        if window is None:
            return

        if MAINTENANCE_PARENT_SENTINEL not in incident.parents:
            incident.parents.append(MAINTENANCE_PARENT_SENTINEL)
            incident.dump()

        if incident.frozen_by_inhibition:
            logger.info(
                "Maintenance match deferred (inhibition holds incident)",
                extra={"uuid": incident.uuid, "window_id": window.id, "until": window.ends_at},
            )
            return

        if incident.frozen_until is not None:
            return

        await self.application.apply_time_freeze(incident, window.ends_at, user=None, queue_=self.queue)
        logger.info(
            "Maintenance time freeze applied",
            extra={"uuid": incident.uuid, "window_id": window.id, "until": window.ends_at},
        )

    async def try_apply_time_freeze_if_window_still_active(self, incident: "Incident"):
        if incident.is_frozen():
            return
        window = self._first_matching_window(incident)
        if window is None:
            self.strip_maintenance_sentinel(incident)
            return
        if MAINTENANCE_PARENT_SENTINEL not in incident.parents:
            incident.parents.append(MAINTENANCE_PARENT_SENTINEL)
        await self.application.apply_time_freeze(incident, window.ends_at, user=None, queue_=self.queue)
        logger.info(
            "Maintenance time freeze applied after inhibition release",
            extra={"uuid": incident.uuid, "window_id": window.id, "until": window.ends_at},
        )

    async def reconcile_on_startup(self):
        for uniq_id in list(self.incidents.uniq_ids.keys()):
            incident = self.incidents.uniq_ids.get(uniq_id)
            if incident is None or incident.status in ("closed", "deleted"):
                continue
            await self.process_incident(incident)

    async def reconcile_active_incidents(self):
        await self.reconcile_on_startup()

    def strip_maintenance_sentinel(self, incident: "Incident") -> bool:
        if MAINTENANCE_PARENT_SENTINEL not in incident.parents:
            return False
        incident.parents.remove(MAINTENANCE_PARENT_SENTINEL)
        incident.dump()
        return True
