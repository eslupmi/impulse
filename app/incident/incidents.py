import os
from typing import Dict, Union

from app.incident.helpers import gen_uuid
from app.incident.incident import Incident, IncidentConfig
from app.logging import logger
from app.ui.incident_websocket import IncidentWS
from config import incidents_path, INCIDENT_ACTUAL_VERSION


class Incidents:
    def __init__(self, incidents_list):
        self.by_uuid: Dict[str, Incident] = {i.uuid: i for i in incidents_list}

    def get(self, alert: Dict) -> Union[Incident, None]:
        uuid_ = gen_uuid(alert.get('groupLabels'))
        return self.by_uuid.get(uuid_)

    def get_by_ts(self, ts: str) -> Union[Incident, None]:
        return next((incident for incident in self.by_uuid.values() if incident.ts == ts), None)

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
            IncidentWS.get_instance().remove_row(incident)
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
