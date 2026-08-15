import os
import threading
from datetime import datetime, UTC
from typing import Any

from icalendar import Calendar, Event, Component

from app.config.config import get_config
from app.config.environment import get_environment_config
from app.logging import logger
from app.maintenance.models import MaintenanceWindow
from app.time import unix_sleep_to_timedelta

import builtins


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


class MaintenanceStore:
    _ICS_FILENAME = "windows.ics"

    def __init__(self):
        env_config = get_environment_config()
        self._dir = os.path.join(env_config.data_path, "maintenance")
        self._file = os.path.join(self._dir, self._ICS_FILENAME)
        self._lock = threading.Lock()
        self._ensure_dir()

    def load_windows(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read_windows_from_disk()

    def save_windows(self, windows: list[dict[str, Any]]) -> bool:
        with self._lock:
            retained = self._filter_retained_windows(windows)
            return self._write_windows_unlocked(retained)

    def list(self) -> list[MaintenanceWindow]:
        windows = self.load_windows()
        return [MaintenanceWindow.from_window_dict(w) for w in windows]

    def prune_expired_windows(self, now: datetime | None = None) -> int:
        with self._lock:
            windows = self._read_windows_from_disk()
            if not windows:
                return 0
            retained, expired = self._partition_by_retention(windows, now)
            if not expired:
                return 0
            self._write_windows_unlocked(retained)
            logger.info(
                "Pruned expired maintenance windows",
                extra={"removed": len(expired)},
            )
            return len(expired)

    def _ensure_dir(self) -> None:
        if not os.path.exists(self._dir):
            os.makedirs(self._dir)
            logger.info("Created maintenance directory", extra={"path": self._dir})

    def _read_windows_from_disk(self) -> builtins.list[dict[str, Any]]:
        if not os.path.exists(self._file):
            return []
        try:
            with open(self._file, "rb") as f:
                cal = Calendar.from_ical(f.read().decode())
            windows = []
            for component in cal.walk():
                if component.name == "VEVENT":
                    window = self._ical_event_to_window(component)
                    if window:
                        windows.append(window)
            return windows
        except Exception as e:
            logger.error("Failed to load maintenance store", extra={"error": str(e), "path": self._file})
            return []

    def _write_windows_unlocked(self, windows: builtins.list[dict[str, Any]]) -> bool:
        try:
            cal = Calendar()
            cal.add("prodid", "-//IMPulse//impulse.maintenance//EN")
            cal.add("version", "2.0")
            cal.add("calscale", "GREGORIAN")
            cal.add("method", "PUBLISH")

            for window in windows:
                event = self._window_to_ical_event(window)
                if event:
                    cal.add_component(event)

            with open(self._file, "wb") as f:
                f.write(cal.to_ical())

            logger.debug("Saved maintenance windows", extra={"count": len(windows)})
            return True
        except Exception as e:
            logger.error("Failed to save maintenance store", extra={"error": str(e), "path": self._file})
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
        except Exception as e:
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
        except Exception as e:
            logger.error("Failed to convert iCal event to maintenance window", extra={"error": str(e)})
            return None

    def _parse_datetime(self, dt_str: str | None) -> datetime | None:
        if isinstance(dt_str, datetime):
            return dt_str
        if not dt_str:
            return None
        try:
            if dt_str.endswith("Z"):
                dt_str = dt_str[:-1] + "+00:00"
            return datetime.fromisoformat(dt_str)
        except Exception:
            return None

    def _retention_cutoff(self, now: datetime) -> datetime:
        config = get_config()
        retention = unix_sleep_to_timedelta(config.incident.timeouts.get("closed"))
        return now - retention

    def _partition_by_retention(
        self, windows: builtins.list[dict[str, Any]], now: datetime | None = None
    ) -> tuple[builtins.list[dict[str, Any]], builtins.list[dict[str, Any]]]:
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

    def _filter_retained_windows(self, windows: builtins.list[dict[str, Any]], now: datetime | None = None) -> builtins.list[dict[str, Any]]:
        retained, _ = self._partition_by_retention(windows, now)
        return retained


_store: MaintenanceStore | None = None


def get_maintenance_store() -> MaintenanceStore:
    global _store
    if _store is None:
        _store = MaintenanceStore()
    return _store
