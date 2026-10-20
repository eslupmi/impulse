import os
import threading
from datetime import UTC, datetime, timedelta
from typing import Any

from icalendar import Calendar, Component, Event

from app.config.config import get_config
from app.config.environment import get_environment_config
from app.logging import logger
from app.maintenance.api import window_from_ws_item
from app.maintenance.models import MaintenanceWindow, _parse_iso
from app.migrator import (
    LEGACY_FILENAME,
    MaintenanceMigrator,
    _read_calendar,
)
from app.time import unix_sleep_to_timedelta


def _ical_dt_to_iso(dt) -> str:
    if hasattr(dt, "isoformat"):
        iso_str = dt.isoformat()
        if not iso_str.endswith("Z") and "+" not in iso_str and "-" not in iso_str[-6:]:
            iso_str += "Z"
        return iso_str
    return str(dt)


def _truncate_summary(matcher: str, max_len: int = 24) -> str:
    if len(matcher) <= max_len:
        return matcher
    return matcher[: max_len - 3] + "..."


def _stored_owner_id(existing: list[dict[str, Any]], payload) -> str | None:
    if not isinstance(payload, dict) or not payload.get("id"):
        return None
    window_id = str(payload["id"])
    for existing_window in existing:
        if existing_window["id"] == window_id:
            return existing_window.get("owner_id")
    return None


def _replace_window(existing: list[dict[str, Any]], window: dict[str, Any]) -> list[dict[str, Any]]:
    merged = []
    replaced = False
    for existing_window in existing:
        if existing_window["id"] == window["id"]:
            merged.append(window)
            replaced = True
        else:
            merged.append(existing_window)
    if not replaced:
        merged.append(window)
    return merged


class MaintenanceStore:
    def __init__(self):
        env_config = get_environment_config()
        self._dir = os.path.join(env_config.data_path, "maintenance")
        self._lock = threading.Lock()
        self._ensure_dir()

    def migrate(self) -> None:
        with self._lock:
            MaintenanceMigrator().upgrade(self)

    def load_windows(self) -> list[dict[str, Any]]:
        with self._lock:
            windows, _paths = self._load_unlocked()
            return windows

    def upsert_window(
        self,
        payload,
        assignable_user_ids: set[str],
    ) -> tuple[bool, list[dict[str, Any]], list[dict[str, Any]]]:
        with self._lock:
            existing, paths = self._load_unlocked()
            window = window_from_ws_item(
                payload,
                assignable_user_ids,
                _stored_owner_id(existing, payload),
            )
            retained = self._filter_retained_windows(_replace_window(existing, window))
            retained_ids = {item["id"] for item in retained}
            if window["id"] in retained_ids and not self._write_kept_window(window, paths):
                return False, existing, existing
            if not self._delete_unretained(existing, paths, retained_ids):
                return False, existing, existing
            return True, existing, retained

    def delete_window(
        self, window_id: str
    ) -> tuple[bool, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None]:
        with self._lock:
            existing, paths = self._load_unlocked()
            deleted = None
            remaining = []
            for existing_window in existing:
                if existing_window["id"] == str(window_id):
                    deleted = existing_window
                else:
                    remaining.append(existing_window)
            if deleted is None:
                return True, existing, existing, None
            retained = self._filter_retained_windows(remaining)
            retained_ids = {item["id"] for item in retained}
            if not self._delete_unretained(existing, paths, retained_ids):
                return False, existing, existing, None
            return True, existing, retained, deleted

    def windows_list(self) -> list[MaintenanceWindow]:
        windows = self.load_windows()
        return [MaintenanceWindow.from_window_dict(w) for w in windows]

    def prune_expired_windows(self, now: datetime | None = None) -> int:
        with self._lock:
            windows, paths = self._load_unlocked()
            if not windows:
                return 0
            _, expired = self._partition_by_retention(windows, now)
            if not expired:
                return 0
            for window in expired:
                self._remove_file(paths[window["id"]])
            logger.info(
                "Pruned expired maintenance windows",
                extra={"removed": len(expired)},
            )
            return len(expired)

    def _write_kept_window(self, window: dict[str, Any], paths: dict[str, str]) -> bool:
        path = paths.get(window["id"])
        if path is None:
            return self._write_window_unlocked(window)
        return self._write_window_file(window, path)

    def _ensure_dir(self) -> None:
        if not os.path.exists(self._dir):
            os.makedirs(self._dir)
            logger.info("Created maintenance directory", extra={"path": self._dir})

    def _load_unlocked(self) -> tuple[list[dict[str, Any]], dict[str, str]]:
        return self._read_individual_windows()

    def _read_individual_windows(self) -> tuple[list[dict[str, Any]], dict[str, str]]:
        windows = []
        paths = {}
        for filename in os.listdir(self._dir):
            if filename == LEGACY_FILENAME or not filename.endswith(".ics"):
                continue
            path = os.path.join(self._dir, filename)
            window = self._read_window_file(path)
            if window is None:
                continue
            windows.append(window)
            paths[window["id"]] = path
        return windows, paths

    def _read_window_file(self, path: str) -> dict[str, Any] | None:
        calendar = _read_calendar(path)
        if calendar is None:
            return None
        for component in calendar.walk():
            if component.name == "VEVENT":
                return self._ical_event_to_window(component)
        return None

    def _allocate_filename(self, created: datetime) -> str:
        moment = created.astimezone(UTC)
        while True:
            filename = moment.strftime("%Y-%m-%d-%H-%M-%S-%f") + ".ics"
            if not os.path.exists(os.path.join(self._dir, filename)):
                return filename
            moment += timedelta(microseconds=1)

    def _new_calendar(self, impulse_version: str) -> Calendar:
        calendar = Calendar()
        calendar.add("prodid", "-//IMPulse//impulse.maintenance//EN")
        calendar.add("version", "2.0")
        calendar.add("calscale", "GREGORIAN")
        calendar.add("method", "PUBLISH")
        calendar.add("x-impulse-version", impulse_version)
        return calendar

    def _write_window_file(self, window: dict[str, Any], path: str) -> bool:
        try:
            calendar = self._new_calendar(MaintenanceMigrator.ACTUAL_VERSION)
            event = self._window_to_ical_event(window)
            if event is None:
                return False
            calendar.add_component(event)
            with open(path, "wb") as f:
                f.write(calendar.to_ical())
            logger.debug("Saved maintenance window", extra={"window_id": window.get("id"), "path": path})
            return True
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to save maintenance window", extra={"error": str(e), "path": path})
            return False

    def _write_legacy_file(self, windows: list[dict[str, Any]]) -> bool:
        path = os.path.join(self._dir, LEGACY_FILENAME)
        try:
            calendar = self._new_calendar(MaintenanceMigrator.LEGACY_VERSION)
            for window in windows:
                event = self._window_to_ical_event(window)
                if event is None:
                    return False
                calendar.add_component(event)
            with open(path, "wb") as f:
                f.write(calendar.to_ical())
            return True
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to write legacy maintenance calendar", extra={"error": str(e), "path": path})
            return False

    def _delete_unretained(
        self,
        existing: list[dict[str, Any]],
        paths: dict[str, str],
        retained_ids: set[str],
    ) -> bool:
        for old in existing:
            if old["id"] in retained_ids:
                continue
            if not self._remove_file(paths[old["id"]]):
                return False
        return True

    def _write_window_unlocked(self, window: dict[str, Any], created: datetime | None = None) -> bool:
        moment = datetime.now(UTC) if created is None else created
        path = os.path.join(self._dir, self._allocate_filename(moment))
        return self._write_window_file(window, path)

    def _remove_file(self, path: str) -> bool:
        try:
            os.remove(path)
            return True
        except OSError as e:
            logger.error("Failed to delete maintenance window", extra={"error": str(e), "path": path})
            return False

    def _window_to_ical_event(self, window: dict[str, Any]) -> Event | None:
        try:
            matchers = window.get("matchers") or []
            if not matchers:
                return None

            event = Event()
            event.add("uid", window.get("id", ""))
            event.add("summary", _truncate_summary(str(matchers[0])))

            start_dt = self._parse_datetime(window.get("start"))
            end_dt = self._parse_datetime(window.get("end"))
            if start_dt is None or end_dt is None:
                return None

            event.add("dtstart", start_dt)
            event.add("dtend", end_dt)
            event.add("dtstamp", datetime.now(UTC))

            for matcher in matchers:
                event.add("x-matcher", str(matcher))

            comment = window.get("comment")
            if comment:
                event.add("x-comment", str(comment))

            owner_id = window.get("owner_id")
            if owner_id:
                event.add("x-owner-id", str(owner_id))

            return event
        except Exception as e:  # noqa: BLE001
            logger.error(
                "Failed to convert maintenance window to iCal event",
                extra={"error": str(e), "window_id": window.get("id")},
            )
            return None

    def _ical_event_to_window(self, event: Component) -> dict[str, Any] | None:
        try:
            uid = event.get("uid")
            if not uid:
                return None

            raw_matchers = event.get("x-matcher")
            if raw_matchers is None:
                matchers = []
            elif isinstance(raw_matchers, list):
                matchers = [str(m) for m in raw_matchers]
            else:
                matchers = [str(raw_matchers)]
            if not matchers:
                logger.error("Skipping maintenance event without matchers", extra={"uid": str(uid)})
                return None

            dtstart = event.get("dtstart")
            dtend = event.get("dtend")
            if not dtstart or not dtend:
                return None

            start_dt = dtstart.dt if hasattr(dtstart, "dt") else dtstart
            end_dt = dtend.dt if hasattr(dtend, "dt") else dtend

            x_comment = event.get("x-comment")
            x_owner_id = event.get("x-owner-id")

            return {
                "id": str(uid),
                "start": _ical_dt_to_iso(start_dt),
                "end": _ical_dt_to_iso(end_dt),
                "matchers": matchers,
                "comment": str(x_comment) if x_comment else "",
                "owner_id": str(x_owner_id) if x_owner_id else None,
            }
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to convert iCal event to maintenance window", extra={"error": str(e)})
            return None

    def _parse_datetime(self, dt_str: str | None) -> datetime | None:
        if isinstance(dt_str, datetime):
            return dt_str
        if not dt_str:
            return None
        try:
            return _parse_iso(dt_str)
        except ValueError:
            return None

    def _retention_cutoff(self, now: datetime) -> datetime:
        config = get_config()
        retention = unix_sleep_to_timedelta(config.incident.timeouts.get("closed"))
        return now - retention

    def _partition_by_retention(
        self, windows: list[dict[str, Any]], now: datetime | None = None
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        now = now or datetime.now(UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        cutoff = self._retention_cutoff(now)
        retained = []
        expired = []
        for window in windows:
            end = self._parse_datetime(window.get("end"))
            if end is None or end < cutoff:
                expired.append(window)
            else:
                retained.append(window)
        return retained, expired

    def _filter_retained_windows(self, windows: list[dict[str, Any]], now: datetime | None = None) -> list[dict[str, Any]]:
        retained, _ = self._partition_by_retention(windows, now)
        return retained


_store: MaintenanceStore | None = None


def get_maintenance_store() -> MaintenanceStore:
    global _store
    if _store is None:
        _store = MaintenanceStore()
    return _store
