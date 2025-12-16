import os
import yaml
from typing import Dict, Union

from app.incident.incident import Incident, IncidentConfig
from app.incident.migrator import IncidentMigrator
from app.logging import logger
from app.ui.websocket import incident_ws
from app.config.config import get_config


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

    def get_by_ts(self, ts: str) -> Union[Incident, None]:
        for uuid_ in self.active_map.values():
            incident = self.uniq_ids.get(uuid_)
            if incident and incident.ts == ts:
                return incident
        return None

    def get_assigned_user_by_id(self, user_id: str) -> Union[str, None]:
        for incident in self.uniq_ids.values():
            if incident.assigned_user_id == user_id and incident.assigned_fullname and incident.assigned_fullname != "-":
                return incident.assigned_fullname
        return None

    def remove_from_active_map(self, uuid: str):
        if uuid in self.active_map:
            incident = self.uniq_ids.get(self.active_map[uuid])
            if incident and incident.is_frozen():
                return
            del self.active_map[uuid]
    
    def unfreeze_incident(self, uniq_id: str):
        """
        Handle incident unfreeze logic.
        Just unfreezes the incident - cleanup is delegated to StatusCheckHandler.
        """
        incident = self.uniq_ids.get(uniq_id)
        if not incident:
            logger.warning(f'Incident with uniq_id {uniq_id} not found for unfreeze')
            return
        
        if not incident.is_frozen():
            logger.info(f'Incident {incident.uuid} is not frozen, skipping unfreeze')
            return
        
        incident.unfreeze()

    def add(self, incident: Incident):
        self.uniq_ids[incident.uniq_id] = incident
        if (incident.status != 'closed' and incident.status != 'deleted') or incident.is_frozen():
            self.active_map[incident.uuid] = incident.uniq_id

    def remove_file(self, incident: Incident):
        config = get_config()
        self.remove_from_active_map(incident.uuid)
        try:
            if incident.status == 'closed' or incident.status == 'deleted':
                closed_str = Incident.datetime_serialize(incident.closed)
                os.remove(f'{config.incidents_path}/{incident.uuid}__{closed_str}.yml')
            else:
                os.remove(f'{config.incidents_path}/{incident.uuid}.yml')
        except (OSError, PermissionError, FileNotFoundError) as e:
            logger.error(f'Failed to delete incident file for uuid: {incident.uuid}: {str(e)}')

    def del_by_uniq_id(self, uniq_id: str):
        incident = self.uniq_ids.pop(uniq_id, None)
        if incident:
            self.remove_file(incident)
            # Schedule async websocket update
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(incident_ws.remove_row(incident))
            except RuntimeError:
                # No event loop running, skip websocket update
                pass
            logger.info(f'Incident {incident.uuid} deleted')
        else:
            logger.warning(f'Incident with uniq_id {uniq_id} not found in the collection.')

    def serialize(self) -> Dict[str, Dict]:
        return {str(uuid_): incident.serialize() for uuid_, incident in self.uniq_ids.items()}

    def get_active_table(self, params):
        return [self.uniq_ids[uniq_id].get_table_data(params) for uniq_id in self.active_map.values()]

    def get_full_table(self, params):
        return [incident.get_table_data(params) for incident in self.uniq_ids.values()]

    @classmethod
    def create_or_load(cls, application_type, application_url, application_team):
        config = get_config()
        # Ensure the incidents directory exists or create it
        if not os.path.exists(config.incidents_path):
            logger.info('Creating incidents directory')
            os.makedirs(config.incidents_path)
        logger.info('Loading existing incidents')

        incidents = cls([])
        migrator = IncidentMigrator()

        for path, _, files in os.walk(config.incidents_path):
            for filename in files:
                file_path = os.path.join(path, filename)

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
                    if incident_.status != 'deleted':
                        incidents.add(incident_)
                    else:
                        os.remove(file_path)
                else:
                    logger.warning(f'Skipping incident {filename}: messenger_type mismatch')

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
