from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING, Tuple

from app.logging import logger
from app.maintenance.models import MaintenanceWindow
from app.maintenance.store import MaintenanceStore
from app.queue.constants import QueueItemType
from app.incident.freeze import FreezeSource, MAINTENANCE_PARENT_SENTINEL
from app.incident.incident import remove_freeze_source
from app.ui.websocket import incident_ws

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

    def _first_matching_window_with_coverage_end(
        self, incident: "Incident", require_future_end: bool = False
    ) -> Optional[Tuple[MaintenanceWindow, datetime]]:
        now = self._now()
        windows = self.store.list()
        active = [w for w in windows if w.is_active(now)]
        active.sort(key=lambda w: (w.starts_at, w.ends_at, w.id))
        for window in active:
            if require_future_end and window.ends_at <= now:
                continue
            if window.matches_incident(incident):
                return window, self._continuous_matching_end(incident, window, windows)
        return None

    def _first_matching_window(
        self, incident: "Incident", require_future_end: bool = False
    ) -> Optional[MaintenanceWindow]:
        match = self._first_matching_window_with_coverage_end(incident, require_future_end)
        return match[0] if match else None

    @staticmethod
    def _continuous_matching_end(
        incident: "Incident", initial_window: MaintenanceWindow, windows: List[MaintenanceWindow]
    ) -> datetime:
        coverage_end = initial_window.ends_at
        candidates = sorted(windows, key=lambda w: (w.starts_at, w.ends_at, w.id))

        extended = True
        while extended:
            extended = False
            for window in candidates:
                if window.ends_at <= coverage_end:
                    continue
                if window.starts_at > coverage_end:
                    continue
                if not window.matches_incident(incident):
                    continue
                coverage_end = window.ends_at
                extended = True

        return coverage_end

    def would_match_active_window(self, incident: "Incident") -> bool:
        return self._first_matching_window(incident) is not None

    def active_windows_payload(self) -> List[dict]:
        now = self._now()
        active = [w for w in self.store.list() if w.is_active(now)]
        active.sort(key=lambda w: w.starts_at)
        return [self._active_window_payload(w) for w in active]

    def _active_window_payload(self, window: MaintenanceWindow) -> dict:
        payload = {
            "start": window.starts_at.isoformat(),
            "end": window.ends_at.isoformat(),
            "comment": window.comment,
        }
        if not window.owner_id:
            return payload

        owner_id = str(window.owner_id)
        payload["owner_id"] = owner_id

        user = self.application.users.get_user_by_id(owner_id)
        if not user or not user.exists:
            payload["owner_full_name"] = owner_id
            return payload

        payload["owner_full_name"] = user.full_name or user.name
        payload["owner_url"] = self.application.get_user_profile_url(owner_id, user)
        return payload

    async def broadcast_active_maintenance(self):
        await incident_ws.broadcast("active_maintenance", self.active_windows_payload())

    async def schedule_window_starts(self):
        now = self._now()
        await self.queue.delete_by_type(QueueItemType.MAINTENANCE_START)
        await self.queue.delete_by_type(QueueItemType.MAINTENANCE_END)
        for window in self.store.list():
            if window.starts_at > now:
                await self.queue.put(
                    window.starts_at,
                    QueueItemType.MAINTENANCE_START,
                    identifier=window.id,
                )
            if window.ends_at > now:
                await self.queue.put(
                    window.ends_at,
                    QueueItemType.MAINTENANCE_END,
                    identifier=window.id,
                )

    async def handle_window_start(self, _window_id: Optional[str]):
        await self.reconcile_all()
        await self.broadcast_active_maintenance()

    async def handle_window_end(self, _window_id: Optional[str]):
        await self.broadcast_active_maintenance()

    async def process_incident(self, incident: "Incident"):
        match = self._first_matching_window_with_coverage_end(incident)
        if match is None:
            return
        window, coverage_end = match

        was_frozen = incident.is_frozen()
        incident.set_maintenance_parent()

        if was_frozen:
            await self._schedule_maintenance_freeze(incident, coverage_end)
            logger.info(
                "Maintenance source recorded on frozen incident",
                extra={"uuid": incident.uuid, "window_id": window.id, "until": coverage_end},
            )
            if incident.ts:
                await self.application.update_incident_message(incident)
            return

        await self.application.apply_time_freeze(
            incident, coverage_end, user=None, queue_=self.queue, source=FreezeSource.MAINTENANCE
        )
        logger.info(
            "Maintenance time freeze applied",
            extra={"uuid": incident.uuid, "window_id": window.id, "until": coverage_end},
        )
        if incident.ts:
            await self.application.update_incident_message(incident)

    async def _schedule_maintenance_freeze(self, incident: "Incident", coverage_end: datetime):
        if incident.frozen_until_source in (None, FreezeSource.MAINTENANCE.value):
            incident.frozen_until = coverage_end
            incident.frozen_until_source = FreezeSource.MAINTENANCE.value
        incident.chain_enabled = False
        incident.dump()

        await self.queue.delete_by_id_type_and_data(
            incident.uniq_id,
            QueueItemType.UNFREEZE,
            FreezeSource.MAINTENANCE.value,
        )
        await self.queue.put(
            coverage_end,
            QueueItemType.UNFREEZE,
            incident.uniq_id,
            data=FreezeSource.MAINTENANCE.value,
        )

    async def reconcile_incident(self, incident: "Incident", update_message: bool = True):
        """Recalculate this incident's maintenance source and time-freeze schedule."""
        match = self._first_matching_window_with_coverage_end(incident, require_future_end=True)
        if match is None:
            await remove_freeze_source(incident, self.queue, source=FreezeSource.MAINTENANCE)
            if update_message and incident.ts:
                await self.application.update_incident_message(incident)
            return
        window, coverage_end = match

        incident.set_maintenance_parent()
        await self._schedule_maintenance_freeze(incident, coverage_end)

        logger.info(
            "Maintenance time freeze scheduled",
            extra={"uuid": incident.uuid, "window_id": window.id, "until": coverage_end},
        )

        if update_message and incident.ts:
            await self.application.update_incident_message(incident)

    async def reconcile_after_window_removed(self, removed_window: MaintenanceWindow):
        for uniq_id in self.incidents.uniq_ids.keys():
            incident = self.incidents.uniq_ids.get(uniq_id)
            if incident is None or incident.status in ("closed", "deleted"):
                continue
            if not removed_window.matches_incident(incident):
                continue
            await self.reconcile_incident(incident)

    @staticmethod
    def _reconcile_fields(window: dict) -> tuple:
        return (
            window["start"],
            window["end"],
            tuple(window.get("matchers", [])),
        )

    def needs_reconcile_after_save(
        self,
        existing: List[Dict[str, Any]],
        saved: List[Dict[str, Any]],
    ) -> bool:
        now = self._now()
        existing_by_id = {w["id"]: w for w in existing}
        for window_dict in saved:
            window = MaintenanceWindow.from_window_dict(window_dict)
            if window.is_active(now):
                return True
            prev = existing_by_id.get(window_dict["id"])
            if prev and self._reconcile_fields(prev) != self._reconcile_fields(window_dict):
                return True
        return False

    async def apply_save_side_effects(
        self,
        existing: List[Dict[str, Any]],
        saved: List[Dict[str, Any]],
        deleted: List[Dict[str, Any]],
    ) -> None:
        for window_dict in deleted:
            await self.reconcile_after_window_removed(
                MaintenanceWindow.from_window_dict(window_dict)
            )
        if self.needs_reconcile_after_save(existing, saved):
            await self.reconcile_all()
        await self.schedule_window_starts()
        await self.broadcast_active_maintenance()

    def _needs_maintenance_reconcile(self, incident: "Incident") -> bool:
        return (
            self.would_match_active_window(incident)
            or MAINTENANCE_PARENT_SENTINEL in incident.parents
            or incident.frozen_until_source == FreezeSource.MAINTENANCE.value
        )

    async def reconcile_all(self):
        for uniq_id in self.incidents.uniq_ids.keys():
            incident = self.incidents.uniq_ids.get(uniq_id)
            if incident is None or incident.status in ("closed", "deleted"):
                continue
            if self._needs_maintenance_reconcile(incident):
                await self.reconcile_incident(incident)
