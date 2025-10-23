import os
import yaml
from typing import Dict, Union

from app.incident.helpers import gen_uuid
from app.incident.incident import Incident, IncidentConfig
from app.incident.migrator import IncidentMigrator
from app.logging import logger
from app.ui.websocket import incident_ws
from app.config.config import get_config


class Incidents:
    def __init__(self, incidents_list):
        self.by_uuid: Dict[str, Incident] = {i.uuid: i for i in incidents_list}

    def get(self, alert: Dict) -> Union[Incident, None]:
        uuid_ = gen_uuid(alert.get('groupLabels'))
        return self.by_uuid.get(uuid_)

    def get_by_ts(self, ts: str) -> Union[Incident, None]:
        return next((incident for incident in self.by_uuid.values() if incident.ts == ts), None)

    def get_assigned_user_by_id(self, user_id: str) -> Union[str, None]:
        """
        Get the assigned_user (full name) from any existing incident with the same user_id.
        This serves as a cache to avoid redundant API calls for user name lookup.
        
        Args:
            user_id: The user ID to search for
            
        Returns:
            The full name if found in any existing incident, None otherwise
        """            
        for incident in self.by_uuid.values():
            if incident.assigned_user_id == user_id and incident.assigned_fullname and incident.assigned_fullname != "-":
                return incident.assigned_fullname
        
        return None

    def add(self, incident: Incident):
        self.by_uuid[incident.uuid] = incident

    def del_by_uuid(self, uuid_: str):
        config = get_config()
        incident = self.by_uuid.pop(uuid_, None)
        if incident:
            try:
                os.remove(f'{config.incidents_path}/{uuid_}.yml')
                logger.info(f'Incident {uuid_} closed. Link: {incident.link}')
            except (OSError, PermissionError, FileNotFoundError) as e:
                logger.error(f'Failed to delete incident file for uuid: {uuid_}: {str(e)}')
            # Schedule async websocket update
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(incident_ws.remove_row(incident))
            except RuntimeError:
                # No event loop running, skip websocket update
                pass
        else:
            logger.warning(f'Incident with uuid: {uuid_} not found in the collection.')

    def serialize(self) -> Dict[str, Dict]:
        return {str(uuid_): incident.serialize() for uuid_, incident in self.by_uuid.items()}

    def get_table(self, params):
        return [incident.get_table_data(params) for incident in self.by_uuid.values()]

    @classmethod
    def create_or_load(cls, application_type, application_url, application_team):
        config = get_config()
        # Ensure the incidents directory exists or create it
        if not os.path.exists(config.incidents_path):
            logger.info('Creating incidents directory')
            try:
                os.makedirs(config.incidents_path)
            except (PermissionError, OSError) as e:
                logger.error(f'Failed to create incidents directory: {config.incidents_path}: {str(e)}')
        logger.info('Loading existing incidents')

        incidents = cls([])
        migrator = IncidentMigrator()

        for path, directories, files in os.walk(config.incidents_path):
            for filename in files:
                file_path = f'{config.incidents_path}/{filename}'

                cls._migrate_file_if_needed(migrator, file_path)

                incident_config = IncidentConfig(
                    application_type=application_type,
                    application_url=application_url,
                    application_team=application_team
                )

                incident_ = Incident.load(
                    dump_file=file_path,
                    incident_config=incident_config
                )
                if incident_.messenger_type == config.messenger.type.value:
                    incidents.add(incident_)
                else:
                    logger.warning(f'Skipping incident {filename}: messenger_type mismatch')
                    continue

        return incidents

    @staticmethod
    def _migrate_file_if_needed(migrator: IncidentMigrator, file_path: str):
        """
        Check if a file needs migration and migrate it if necessary.

        Args:
            migrator: The IncidentMigrator instance
            file_path: Path to the incident file
        """
        config = get_config()
        try:
            with open(file_path, 'r') as f:
                content = yaml.load(f, Loader=yaml.CLoader)
                current_version = content.get('version', 'v0.4')

            if current_version != config.INCIDENT_ACTUAL_VERSION:
                migrator.migrate_file(file_path, content, current_version, config.INCIDENT_ACTUAL_VERSION)

        except Exception as e:
            logger.error(f'Failed to check/migrate file {file_path}: {str(e)}')
            raise
