import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from icalendar import Calendar, Component

from app.logging import logger

if TYPE_CHECKING:
    from app.maintenance.store import MaintenanceStore

LEGACY_FILENAME = "windows.ics"


class MaintenanceMigrator:
    def migrate(self, store: "MaintenanceStore") -> None:
        path = os.path.join(store._dir, LEGACY_FILENAME)
        if not os.path.exists(path):
            return

        logger.info("Migrating maintenance windows", extra={"path": path})
        try:
            with open(path, "rb") as f:
                calendar = Calendar.from_ical(f.read().decode())
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to read legacy maintenance calendar", extra={"error": str(e), "path": path})
            return

        existing_ids = {window["id"] for window in store._read_individual_windows()[0]}
        written = 0
        for component in calendar.walk():
            if component.name != "VEVENT":
                continue
            window = store._ical_event_to_window(component)
            if window is None or window["id"] in existing_ids:
                continue
            if not store._write_window_unlocked(window, _created_from_event(component)):
                return
            existing_ids.add(window["id"])
            written += 1

        if not store._remove_file(path):
            return
        logger.info("Migrated maintenance windows", extra={"count": written})


def _created_from_event(event: Component) -> datetime:
    raw = event.get("dtstamp")
    if raw is None:
        raw = event.get("dtstart")
    value = raw.dt if hasattr(raw, "dt") else raw
    if not isinstance(value, datetime):
        value = datetime(value.year, value.month, value.day)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
