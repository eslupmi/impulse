import os
from typing import Dict, Union

from app.incident.helpers import gen_uuid
from app.incident.incident import Incident, IncidentConfig
from app.logging import logger
from app.ui.websocket import incident_ws
from config import incidents_path, INCIDENT_ACTUAL_VERSION


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
        incident = self.by_uuid.pop(uuid_, None)
        if incident:
            try:
                os.remove(f'{incidents_path}/{uuid_}.yml')
                logger.info(f'Incident {uuid_} closed. Link: {incident.link}')
            except FileNotFoundError:
                logger.error(f'Failed to delete incident file for uuid: {uuid_}. File not found.')
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
        # Ensure the incidents directory exists or create it
        if not os.path.exists(incidents_path):
            logger.info('Creating incidents directory')
            os.makedirs(incidents_path)
        logger.info('Loading existing incidents')

        incidents = cls([])

        # Walk through the directory and load each incident
        for path, directories, files in os.walk(incidents_path):
            for filename in files:
                config = IncidentConfig(
                    application_type=application_type,
                    application_url=application_url,
                    application_team=application_team
                )

                incident_ = Incident.load(
                    dump_file=f'{incidents_path}/{filename}',
                    config=config
                )
                if incident_.version != INCIDENT_ACTUAL_VERSION:
                    cls.update_incident(incident_)
                incidents.add(incident_)

        return incidents

    @staticmethod
    def update_incident(incident: Incident):
        logger.info(f'Updating incident with uuid {incident.uuid} to version {INCIDENT_ACTUAL_VERSION}')
        incident.version = INCIDENT_ACTUAL_VERSION
        incident.dump()
