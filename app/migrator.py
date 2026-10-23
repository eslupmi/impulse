import os
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar

import yaml
from icalendar import Calendar

from app.config.config import MAINTENANCE_SCHEMA_VERSION, get_config
from app.config.environment import get_environment_config
from app.incident.freeze import FreezeSource
from app.incident.incident import Incident
from app.logging import logger
from app.tools import NoAliasDumper

if TYPE_CHECKING:
    from app.maintenance.store import MaintenanceStore

DOWNGRADE_FLOOR = 'v3.6.0'
_VERSION_RE = re.compile(r'^v(\d+)\.(\d+)\.(\d+)$')


class IncidentMigrator:
    """
    Handles versioned migrations for incident files.

    This migrator works directly with YAML files before they are loaded
    into Incident objects, allowing for breaking changes like field renames.
    """

    # Define migration path - each version knows how to migrate to the next
    MIGRATION_CHAIN: ClassVar[dict[str, str]] = {
        'v0.4': 'v3.0.0',
        'v3.0.0': 'v3.2.0',
        'v3.2.0': 'v3.4.0',
        'v3.4.0': 'v3.6.0',
        'v3.6.0': 'v3.7.0',
    }
    REVERSE_MIGRATION_CHAIN: ClassVar[dict[str, str]] = {dst: src for src, dst in MIGRATION_CHAIN.items()}

    def __init__(self):
        """Initialize the migrator with available migration methods."""
        self._migration_methods = {
            'v0.4_to_v3.0.0': self._migrate_v0_4_to_v3_0_0,
            'v3.0.0_to_v3.2.0': self._migrate_v3_0_0_to_v3_2_0,
            'v3.2.0_to_v3.4.0': self._migrate_v3_2_0_to_v3_4_0,
            'v3.4.0_to_v3.6.0': self._migrate_v3_4_0_to_v3_6_0,
            'v3.6.0_to_v3.7.0': self._migrate_v3_6_0_to_v3_7_0,
            'v3.7.0_to_v3.6.0': self._migrate_v3_7_0_to_v3_6_0,
        }
        self._filename_migration_methods = {
            'v3.6.0_to_v3.7.0': self._migrate_filename_v3_6_0_to_v3_7_0,
            'v3.7.0_to_v3.6.0': self._migrate_filename_v3_7_0_to_v3_6_0,
        }

    def migrate_file(self, file_path: str, incident_data: dict, current_version: str, target_version: str) -> str:
        """
        Migrate an incident file to the target version.

        Args:
            file_path: Path to the incident YAML file
            incident_data: The loaded incident data
            current_version: Current version of the incident data
            target_version: The target version to migrate to

        Returns:
            Final path to the incident file (may differ after filename migration)
        """
        logger.info(f'Migrating {os.path.basename(file_path)} from {current_version} to {target_version}')

        migrated_data = self._migrate_data(incident_data, current_version, target_version)

        try:
            with open(file_path, 'w') as f:
                yaml.dump(migrated_data, f, NoAliasDumper, default_flow_style=False)
        except (OSError, PermissionError, FileNotFoundError) as e:
            logger.error(f'Failed to write migrated incident file {os.path.basename(file_path)}: {e}')
            return file_path

        final_path = self._apply_filename_migrations(file_path, migrated_data, current_version, target_version)
        logger.info(f'Successfully migrated {os.path.basename(final_path)}')
        return final_path

    ### PRIVATE METHODS ###

    def _migrate_data(self, incident_data: dict, from_version: str, to_version: str) -> dict:
        """
        Apply sequential migrations from from_version to to_version.

        Args:
            incident_data: The incident data dictionary to migrate
            from_version: The current version of the incident data
            to_version: The target version to migrate to

        Returns:
            The migrated incident data dictionary
        """
        if not self.MIGRATION_CHAIN:
            incident_data['version'] = to_version
            return incident_data

        migration_path = self._get_migration_path(from_version, to_version)

        current_data = incident_data.copy()

        for i in range(len(migration_path) - 1):
            current_version = migration_path[i]
            next_version = migration_path[i + 1]

            current_data = self._apply_single_migration(current_data, current_version, next_version)
        return current_data

    def _get_migration_path(self, from_version: str, to_version: str) -> list[str]:
        """
        Find the migration path from from_version to to_version (upgrade or downgrade).

        Args:
            from_version: Starting version
            to_version: Target version

        Returns:
            List of versions in migration path
        """
        if from_version == to_version:
            return [from_version]

        forward = self._walk_chain(from_version, to_version, self.MIGRATION_CHAIN)
        if forward is not None:
            return forward

        reverse = self._walk_chain(from_version, to_version, self.REVERSE_MIGRATION_CHAIN)
        if reverse is not None:
            return reverse

        raise ValueError(f'No migration path from {from_version} to {to_version}')

    @staticmethod
    def _walk_chain(from_version: str, to_version: str, chain: dict[str, str]) -> list[str] | None:
        path = [from_version]
        current = from_version
        while current != to_version:
            next_version = chain.get(current)
            if next_version is None:
                return None
            path.append(next_version)
            current = next_version
        return path

    def _apply_single_migration(self, data: dict, from_version: str, to_version: str) -> dict:
        """
        Apply a single migration step.

        Args:
            data: The incident data to migrate
            from_version: Current version
            to_version: Target version for this step

        Returns:
            The migrated data
        """
        method_key = f"{from_version}_to_{to_version}"
        migration_method = self._migration_methods[method_key]
        migrated_data = migration_method(data)
        migrated_data['version'] = to_version
        return migrated_data

    @staticmethod
    def _migrate_v0_4_to_v3_0_0(data: dict) -> dict:
        migrated = data.copy()
        migrated['payload'] = migrated.pop('last_state')

        config = get_config()
        migrated['messenger_type'] = config.messenger.type
        return migrated

    @staticmethod
    def _to_aware_utc(value):
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=UTC)
            return value.astimezone(UTC)
        return value

    def _migrate_v3_0_0_to_v3_2_0(self, data: dict) -> dict:
        migrated = data.copy()

        for key in ('status_update_datetime', 'updated', 'created'):
            if key in migrated:
                migrated[key] = self._to_aware_utc(migrated.get(key))

        chain = migrated.get('chain') or []
        new_chain = []
        for step in chain:
            step_copy = step.copy()
            if 'datetime' in step_copy:
                step_copy['datetime'] = self._to_aware_utc(step_copy.get('datetime'))
            new_chain.append(step_copy)
        migrated['chain'] = new_chain

        migrated['uniq_id'] = Incident.gen_uniq_id(
            migrated.get('payload', {}).get('groupLabels', {}),
            migrated.get('created')  # type: ignore[arg-type]
        )

        return migrated

    @staticmethod
    def _migrate_v3_2_0_to_v3_4_0(data: dict) -> dict:
        """Migrate chain steps from absolute datetime to relative delay.
        Computes delay as the difference from the first step's datetime.
        Sets chain_active_seconds to the delay of the last completed step."""
        migrated = data.copy()

        chain = migrated.get('chain') or []
        if chain and 'datetime' in chain[0] and 'delay' not in chain[0]:
            first_dt = chain[0].get('datetime')
            new_chain = []
            last_done_delay = 0.0
            for step in chain:
                step_copy = step.copy()
                step_dt = step_copy.pop('datetime', None)
                if first_dt is not None and step_dt is not None:
                    step_copy['delay'] = (step_dt - first_dt).total_seconds()
                else:
                    step_copy['delay'] = 0.0
                if step_copy.get('done') and step_copy['delay'] > last_done_delay:
                    last_done_delay = step_copy['delay']
                new_chain.append(step_copy)
            migrated['chain'] = new_chain
            migrated['chain_active_seconds'] = last_done_delay
        else:
            migrated.setdefault('chain_active_seconds', 0.0)

        return migrated

    @staticmethod
    def _migrate_v3_4_0_to_v3_6_0(data: dict) -> dict:
        """Add frozen_until_source for source-aware time freeze ownership."""
        migrated = data.copy()
        if migrated.get('frozen_until') is not None and migrated.get('frozen_until_source') is None:
            migrated['frozen_until_source'] = FreezeSource.TIME.value
        else:
            migrated.setdefault('frozen_until_source', None)
        return migrated

    @staticmethod
    def reshape_chain_steps(data: dict) -> dict:
        if 'chain' not in data and 'chain_steps' not in data:
            return data

        migrated = data.copy()
        chain = migrated.pop('chain', None)
        if chain is None:
            chain = migrated.get('chain_steps', [])

        new_steps = []
        for step in chain:
            step_copy = step.copy()
            if 'type' in step_copy:
                step_copy['name'] = step_copy.pop('type')
            if 'identifier' in step_copy:
                step_copy['value'] = step_copy.pop('identifier')
            if step_copy.get('name') == 'webhook' and 'status' not in step_copy:
                result = step_copy.get('result')
                step_copy['status'] = 'ok' if isinstance(result, int) else None
            new_steps.append(step_copy)

        migrated['chain_steps'] = new_steps
        migrated.pop('chain', None)
        return migrated

    @staticmethod
    def reshape_chain_steps_v3_6(data: dict) -> dict:
        if 'chain' not in data and 'chain_steps' not in data:
            return data

        migrated = data.copy()
        steps = migrated.pop('chain_steps', None)
        if steps is None:
            steps = migrated.get('chain', [])

        new_chain = []
        for step in steps:
            step_copy = step.copy()
            if 'name' in step_copy:
                step_copy['type'] = step_copy.pop('name')
            if 'value' in step_copy:
                step_copy['identifier'] = step_copy.pop('value')
            step_copy.pop('status', None)
            new_chain.append(step_copy)

        migrated['chain'] = new_chain
        migrated.pop('chain_steps', None)
        return migrated

    @staticmethod
    def _migrate_v3_6_0_to_v3_7_0(data: dict) -> dict:
        return IncidentMigrator.reshape_chain_steps(data)

    @staticmethod
    def _migrate_v3_7_0_to_v3_6_0(data: dict) -> dict:
        return IncidentMigrator.reshape_chain_steps_v3_6(data)

    def _apply_filename_migrations(self, file_path: str, incident_data: dict, from_version: str, to_version: str) -> str:
        if not self.MIGRATION_CHAIN:
            return file_path

        migration_path = self._get_migration_path(from_version, to_version)
        current_path = file_path

        for i in range(len(migration_path) - 1):
            current_version = migration_path[i]
            next_version = migration_path[i + 1]
            method_key = f"{current_version}_to_{next_version}"
            filename_method = self._filename_migration_methods.get(method_key)
            if filename_method:
                current_path = filename_method(current_path, incident_data)

        return current_path

    @staticmethod
    def _migrate_filename_v3_6_0_to_v3_7_0(file_path: str, incident_data: dict) -> str:
        uniq_id = incident_data['uniq_id']
        new_path = os.path.join(os.path.dirname(file_path), f'{uniq_id}.yml')
        return IncidentMigrator._rename_file(file_path, new_path)

    @staticmethod
    def _migrate_filename_v3_7_0_to_v3_6_0(file_path: str, incident_data: dict) -> str:
        uuid = Incident.gen_uuid(incident_data.get('payload', {}).get('groupLabels', {}))
        status = incident_data.get('status')
        closed = incident_data.get('closed')
        if status in ('closed', 'deleted') and isinstance(closed, datetime):
            closed_str = closed.strftime('%Y_%m_%d__%H_%M_%S')
            basename = f'{uuid}__{closed_str}.yml'
        else:
            basename = f'{uuid}.yml'
        new_path = os.path.join(os.path.dirname(file_path), basename)
        return IncidentMigrator._rename_file(file_path, new_path)

    @staticmethod
    def _rename_file(old_path: str, new_path: str) -> str:
        if old_path == new_path:
            return old_path
        logger.info(f'Renaming incident file {os.path.basename(old_path)} to {os.path.basename(new_path)}')
        os.rename(old_path, new_path)
        return new_path

    @classmethod
    def schema_versions(cls) -> set:
        return set(cls.MIGRATION_CHAIN.keys()) | set(cls.MIGRATION_CHAIN.values())

    @classmethod
    def resolve_downgrade_target(cls, version_arg: str | None) -> str:
        """Resolve CLI --downgrade argument to a schema version."""
        if version_arg is None or version_arg == '':
            actual = get_config().INCIDENT_ACTUAL_VERSION
            previous = cls.REVERSE_MIGRATION_CHAIN.get(actual)
            if previous is None:
                raise ValueError(f'No previous schema version to downgrade from {actual}')
            target = previous
        else:
            target = cls._map_release_to_schema(version_arg)

        if not cls._version_at_or_above_floor(target):
            raise ValueError(
                f'Downgrade target {target} is below supported floor {DOWNGRADE_FLOOR}'
            )
        return target

    @classmethod
    def _map_release_to_schema(cls, version: str) -> str:
        schemas = cls.schema_versions()
        if version in schemas:
            return version

        match = _VERSION_RE.match(version)
        if not match:
            raise ValueError(f'Unknown version: {version}')

        major, minor, _ = match.groups()
        prefix = f'v{major}.{minor}.'
        candidates = sorted(
            v for v in schemas
            if v.startswith(prefix) and _VERSION_RE.match(v)
        )
        if not candidates:
            raise ValueError(f'No schema version for release {version}')
        return candidates[0]

    @staticmethod
    def _version_at_or_above_floor(version: str) -> bool:
        match = _VERSION_RE.match(version)
        if not match:
            return False
        floor = _VERSION_RE.match(DOWNGRADE_FLOOR)
        if floor is None:
            return False
        return tuple(int(x) for x in match.groups()) >= tuple(int(x) for x in floor.groups())

    @staticmethod
    def _version_newer_than(current: str, target: str) -> bool:
        """Return True if current is strictly newer than target along the migration chain."""
        if current == target:
            return False
        return IncidentMigrator._walk_chain(
            current, target, IncidentMigrator.REVERSE_MIGRATION_CHAIN
        ) is not None


def downgrade_incidents_only(version_arg: str | None = None) -> None:
    """Downgrade all incident files to the resolved target schema and exit."""
    try:
        target_version = IncidentMigrator.resolve_downgrade_target(version_arg)
    except ValueError as e:
        logger.error(str(e))
        raise SystemExit(1)

    env_config = get_environment_config()
    incidents_path = env_config.incidents_path
    if not os.path.exists(incidents_path):
        logger.info(f'Incidents directory does not exist: {incidents_path}')
        return

    migrator = IncidentMigrator()
    logger.info(f'Downgrading incident files to {target_version}')

    for path, _, files in os.walk(incidents_path):
        for filename in files:
            file_path = os.path.join(path, filename)
            with open(file_path, 'r') as f:
                content = yaml.load(f, Loader=yaml.CLoader)
            current_version = content.get('version', 'v0.4')

            if not IncidentMigrator._version_newer_than(current_version, target_version):
                continue

            migrator.migrate_file(file_path, content, current_version, target_version)

    logger.info(f'Downgrade to {target_version} complete')


LEGACY_FILENAME = "windows.ics"


class MaintenanceMigrator:
    ACTUAL_VERSION = MAINTENANCE_SCHEMA_VERSION
    LEGACY_VERSION = "v3.7.0"

    # shortcut: one maintenance schema transition; add a chain when another transition is introduced.
    @classmethod
    def resolve_downgrade_target(cls, version_arg: str | None) -> str:
        if version_arg is None or version_arg == '':
            return cls.LEGACY_VERSION
        versions = (cls.LEGACY_VERSION, cls.ACTUAL_VERSION)
        if version_arg in versions:
            return version_arg
        match = _VERSION_RE.match(version_arg)
        if not match:
            raise ValueError(f'Unknown version: {version_arg}')
        for version in versions:
            if version.startswith(f'v{match[1]}.{match[2]}.'):
                return version
        raise ValueError(f'No schema version for release {version_arg}')

    def upgrade(self, store: "MaintenanceStore") -> None:
        legacy_path = os.path.join(store._dir, LEGACY_FILENAME)
        target = self.ACTUAL_VERSION
        current = target
        if os.path.exists(legacy_path):
            current = _path_version(legacy_path) or self.LEGACY_VERSION
            if current not in (self.LEGACY_VERSION, target):
                raise ValueError(f'No migration path from {current} to {target}')
        self._rename_individual_files(store)
        if current != target:
            logger.info("Migrating maintenance windows", extra={"from": current, "to": target})
            self._split_legacy(store)
        self._stamp_missing_version(store, target)

    def downgrade(self, store: "MaintenanceStore", target: str) -> None:
        current = self._individual_version(store)
        if current == self.ACTUAL_VERSION and target == self.LEGACY_VERSION:
            logger.info("Downgrading maintenance windows", extra={"from": current, "to": target})
            self._merge_legacy(store)

    @staticmethod
    def _rename_individual_files(store: "MaintenanceStore") -> None:
        _windows, paths = store._read_individual_windows()
        for window_id, path in paths.items():
            target = store._window_path(window_id)
            if path == target:
                continue
            if os.path.lexists(target):
                raise FileExistsError(f'Maintenance filename is already occupied: {target}')
            os.rename(path, target)

    def _split_legacy(self, store: "MaintenanceStore") -> None:
        path = os.path.join(store._dir, LEGACY_FILENAME)
        if not os.path.exists(path):
            return
        calendar = _read_calendar(path)
        if calendar is None:
            return

        existing_ids = {window["id"] for window in store._read_individual_windows()[0]}
        written = 0
        for window in _windows_in_calendar(store, calendar, existing_ids):
            if not store._write_window_unlocked(window):
                return
            written += 1

        if not store._remove_file(path):
            return
        logger.info("Migrated maintenance windows", extra={"count": written})

    def _merge_legacy(self, store: "MaintenanceStore") -> None:
        _windows, paths = store._read_individual_windows()
        windows = []
        seen: set[str] = set()
        for path in paths.values():
            calendar = _read_calendar(path)
            if calendar is None:
                return
            windows.extend(_windows_in_calendar(store, calendar, seen))
        legacy_path = os.path.join(store._dir, LEGACY_FILENAME)
        if os.path.exists(legacy_path):
            calendar = _read_calendar(legacy_path)
            if calendar is None:
                return
            windows.extend(_windows_in_calendar(store, calendar, seen))
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
            return _path_version(os.path.join(store._dir, filename)) or self.ACTUAL_VERSION
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


def _windows_in_calendar(store: "MaintenanceStore", calendar: Calendar | None, seen: set[str]) -> list:
    if calendar is None:
        return []
    found = []
    for component in calendar.walk():
        if component.name != "VEVENT":
            continue
        window = store._ical_event_to_window(component)
        if window is None or window["id"] in seen:
            continue
        window["_dtstamp"] = component.get("dtstamp")
        found.append(window)
        seen.add(window["id"])
    return found


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
