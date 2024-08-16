import json
import os
import uuid

from app import logger
from app.incident import Incidents, Incident, actual_version, update_incident
from app.incident.incident import IncidentConfig
from config import incidents_path


def gen_uuid(data):
    return uuid.uuid5(uuid.NAMESPACE_OID, json.dumps(data))


def create_or_load_incidents(application_type, application_url, application_team):
    if not os.path.exists(incidents_path):
        logger.debug(f'creating incidents_directory')
        os.makedirs(incidents_path)
        logger.debug(f'created incidents_directory')
    else:
        logger.debug(f'load incidents from disk')

    incidents = Incidents([])
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
            if incident_.version != actual_version:
                update_incident(incident_)
            incidents.add(incident_)

    return incidents
