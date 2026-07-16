import os
from typing import Dict, Union

import yaml

from app.config.config import get_config
from app.config.environment import get_environment_config
from app.incident.incident import Incident, IncidentConfig
from app.incident.migrator import IncidentMigrator
from app.logging import logger
from app.ui.websocket import incident_ws


class Incidents:
    def __init__(self, incidents_list):
        self.active_map: Dict[str, str] = {}  # {uuid: uniq_id}
        self.uniq_ids: Dict[str, Incident] = {}
        for i in incidents_list:
            self.uniq_ids[i.uniq_id] = i
            if (i.status != 'closed' and i.status != 'deleted') or i.is_frozen():
                self.active_map[i.uuid] = i.uniq_id

    def get(self, alert: Dict) -> Union[Incident, None]:
        uuid = Incident.gen_uuid(alert.get('groupLabels'))
        return self.get_by_uuid(uuid)

    def get_by_uuid(self, uuid: str) -> Union[Incident, None]:
        uniq_id = self.active_map.get(uuid)
        return self.uniq_ids.get(uniq_id)

    def get_by_uniq_id(self, uniq_id: str) -> Union[Incident, None]:
        return self.uniq_ids.get(uniq_id)

    def get_by_ts(self, ts: str) -> Union[Incident, None]:
        for uuid_ in self.active_map.values():
            incident = self.uniq_ids.get(uuid_)
            if incident and incident.ts == ts:
                return incident
        return None

    def remove_from_active_map(self, uuid: str):
        if uuid in self.active_map:
            incident = self.uniq_ids.get(self.active_map[uuid])
            if incident and incident.is_frozen():
                return
            del self.active_map[uuid]
    
    def add(self, incident: Incident):
        self.uniq_ids[incident.uniq_id] = incident
        if (incident.status != 'closed' and incident.status != 'deleted') or incident.is_frozen():
            self.active_map[incident.uuid] = incident.uniq_id

    def remove_file(self, incident: Incident):
        self.remove_from_active_map(incident.uuid)
        try:
            incident_filename = incident.get_current_filename()
            os.remove(incident_filename)
        except (OSError, PermissionError, FileNotFoundError) as e:
            logger.error(f'Failed to delete incident file for uniq_id: {incident.uniq_id}: {str(e)}')

    def del_by_uniq_id(self, uniq_id: str):
        incident = self.uniq_ids.pop(uniq_id, None)
        if incident:
            self.remove_file(incident)
            # Schedule async websocket update
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    _ws_task = asyncio.create_task(incident_ws.remove_row(incident))
            except RuntimeError:
                # No event loop running, skip websocket update
                pass
            logger.info("Incident deleted", extra={'uniq_id': incident.uniq_id})
        else:
            logger.warning("Incident not found", extra={'uniq_id': uniq_id})

    def serialize(self) -> Dict[str, Dict]:
        return {str(uuid_): incident.serialize() for uuid_, incident in self.uniq_ids.items()}

    def get_active_table(self, params):
        return [self.uniq_ids[uniq_id].get_table_data(params) for uniq_id in self.active_map.values()]

    def get_full_table(self, params):
        return [incident.get_table_data(params) for incident in self.uniq_ids.values()]

    @classmethod
    def create_or_load(cls, application_type, application_url, application_team):
        config = get_config()
        env_config = get_environment_config()
        # Ensure the incidents directory exists or create it
        if not os.path.exists(env_config.incidents_path):
            logger.info('Creating incidents directory')
            os.makedirs(env_config.incidents_path)
        logger.info('Loading existing incidents')

        incidents = cls([])
        migrator = IncidentMigrator()

        for path, _, files in os.walk(env_config.incidents_path):
            for filename in files:
                file_path = os.path.join(path, filename)

                file_path = cls._migrate_file_if_needed(migrator, file_path)

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
                    if incident_.status != 'deleted' or incident_.is_frozen():
                        incidents.add(incident_)
                    else:
                        os.remove(file_path)
                else:
                    logger.warning(f'Skipping incident {filename}: messenger_type mismatch')

        return incidents

    ### PRIVATE METHODS ###

    @staticmethod
    def _migrate_file_if_needed(migrator: IncidentMigrator, file_path: str) -> str:
        """
        Check if a file needs migration and migrate it if necessary.

        Args:
            migrator: The IncidentMigrator instance
            file_path: Path to the incident file
            
        Returns:
            Path to the incident file (may differ after filename migration)
        """
        config = get_config()
        try:
            with open(file_path, 'r') as f:
                content = yaml.load(f, Loader=yaml.CLoader)
                current_version = content.get('version', 'v0.4')

            if current_version != config.INCIDENT_ACTUAL_VERSION:
                return migrator.migrate_file(file_path, content, current_version, config.INCIDENT_ACTUAL_VERSION)
            return file_path

        except Exception as e:
            logger.error(f'Failed to check/migrate file {file_path}: {str(e)}')
            raise
