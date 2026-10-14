import os
from datetime import datetime, timezone
from typing import ClassVar

import yaml

from app.config.config import get_config
from app.config.environment import get_environment_config
from app.incident.freeze import FreezeSource
from app.incident.incident import Incident
from app.logging import logger
from app.schema_migrator import SchemaMigrator
from app.tools import NoAliasDumper


class IncidentMigrator(SchemaMigrator):
    """
    Handles versioned migrations for incident files.
    
    This migrator works directly with YAML files before they are loaded
    into Incident objects, allowing for breaking changes like field renames.
    """

    DOWNGRADE_FLOOR = 'v3.6.0'
    MIGRATION_CHAIN: ClassVar[dict[str, str]] = {
        'v0.4': 'v3.0.0',
        'v3.0.0': 'v3.2.0',
        'v3.2.0': 'v3.4.0',
        'v3.4.0': 'v3.6.0',
        'v3.6.0': 'v3.7.0',
    }

    @classmethod
    def schema_version(cls) -> str:
        return get_config().INCIDENT_ACTUAL_VERSION
    
    def __init__(self):
        super().__init__()
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
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
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
