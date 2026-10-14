import os
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar

from icalendar import Calendar, Component

from app.logging import logger
from app.maintenance.models import _ensure_utc
from app.schema_migrator import SchemaMigrator

if TYPE_CHECKING:
    from app.maintenance.store import MaintenanceStore

LEGACY_FILENAME = "windows.ics"


class MaintenanceMigrator(SchemaMigrator):
    ACTUAL_VERSION = "v3.8.0"
    LEGACY_VERSION = "v3.7.0"
    DOWNGRADE_FLOOR = LEGACY_VERSION
    MIGRATION_CHAIN: ClassVar[dict[str, str]] = {
        LEGACY_VERSION: ACTUAL_VERSION,
    }

    def __init__(self):
        super().__init__()
        self._migration_methods = {
            "v3.7.0_to_v3.8.0": self._split_legacy,
            "v3.8.0_to_v3.7.0": self._merge_legacy,
        }

    @classmethod
    def actual_version(cls) -> str:
        return cls.ACTUAL_VERSION

    def upgrade(self, store: "MaintenanceStore") -> None:
        legacy_path = os.path.join(store._dir, LEGACY_FILENAME)
        target = self.actual_version()
        if os.path.exists(legacy_path):
            current = _path_version(legacy_path) or self.LEGACY_VERSION
            if current != target:
                logger.info("Migrating maintenance windows", extra={"from": current, "to": target})
                self._apply_steps(store, current, target)
        self._stamp_missing_version(store, target)

    def downgrade(self, store: "MaintenanceStore", target: str) -> None:
        current = self._individual_version(store)
        if current is None or not self._version_newer_than(current, target):
            return
        logger.info("Downgrading maintenance windows", extra={"from": current, "to": target})
        self._apply_steps(store, current, target)

    def _apply_steps(self, store: "MaintenanceStore", from_version: str, to_version: str) -> None:
        migration_path = self._get_migration_path(from_version, to_version)
        for i in range(len(migration_path) - 1):
            method_key = f"{migration_path[i]}_to_{migration_path[i + 1]}"
            self._migration_methods[method_key](store)

    def _split_legacy(self, store: "MaintenanceStore") -> None:
        path = os.path.join(store._dir, LEGACY_FILENAME)
        if not os.path.exists(path):
            return
        calendar = _read_calendar(path)
        if calendar is None:
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

    def _merge_legacy(self, store: "MaintenanceStore") -> None:
        windows, paths = store._read_individual_windows()
        legacy_path = os.path.join(store._dir, LEGACY_FILENAME)
        if os.path.exists(legacy_path):
            calendar = _read_calendar(legacy_path)
            seen = {window["id"] for window in windows}
            if calendar is not None:
                for component in calendar.walk():
                    if component.name != "VEVENT":
                        continue
                    window = store._ical_event_to_window(component)
                    if window is None or window["id"] in seen:
                        continue
                    windows.append(window)
                    seen.add(window["id"])
        if not store._write_legacy_file(windows):
            return
        for path in paths.values():
            if not store._remove_file(path):
                return
        logger.info("Downgraded maintenance windows", extra={"count": len(windows)})

    def _individual_version(self, store: "MaintenanceStore") -> str | None:
        for filename in os.listdir(store._dir):
            if filename == LEGACY_FILENAME or not filename.endswith(".ics"):
                continue
            return _path_version(os.path.join(store._dir, filename)) or self.actual_version()
        return None

    def _stamp_missing_version(self, store: "MaintenanceStore", version: str) -> None:
        for filename in os.listdir(store._dir):
            if filename == LEGACY_FILENAME or not filename.endswith(".ics"):
                continue
            path = os.path.join(store._dir, filename)
            calendar = _read_calendar(path)
            if calendar is None or _calendar_version(calendar) is not None:
                continue
            calendar.add("x-impulse-version", version)
            with open(path, "wb") as f:
                f.write(calendar.to_ical())


def downgrade_maintenance(version_arg: str | None = None) -> None:
    try:
        target_version = MaintenanceMigrator.resolve_downgrade_target(version_arg)
    except ValueError as e:
        logger.error(str(e))
        raise SystemExit(1)

    from app.maintenance.store import get_maintenance_store

    store = get_maintenance_store()
    logger.info(f"Downgrading maintenance windows to {target_version}")
    MaintenanceMigrator().downgrade(store, target_version)
    logger.info(f"Downgrade to {target_version} complete")


def _read_calendar(path: str) -> Calendar | None:
    try:
        with open(path, "rb") as f:
            parsed = Calendar.from_ical(f.read().decode())
    except Exception as e:  # noqa: BLE001
        logger.error("Failed to read maintenance calendar", extra={"error": str(e), "path": path})
        return None
    if not isinstance(parsed, Calendar):
        return None
    return parsed


def _calendar_version(calendar: Calendar) -> str | None:
    raw = calendar.get("x-impulse-version")
    if raw is None:
        return None
    return str(raw)


def _path_version(path: str) -> str | None:
    calendar = _read_calendar(path)
    if calendar is None:
        return None
    return _calendar_version(calendar)


def _created_from_event(event: Component) -> datetime:
    raw = event.get("dtstamp")
    if raw is None:
        raw = event.get("dtstart")
    value = raw.dt if hasattr(raw, "dt") else raw
    if not isinstance(value, datetime):
        value = datetime(value.year, value.month, value.day)
    return _ensure_utc(value)
