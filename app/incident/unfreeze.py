from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.im.template import notification_unfreeze
from app.jinja_template import JinjaTemplate
from app.logging import logger
from app.queue.constants import QueueItemType

if TYPE_CHECKING:
    from app.incident.incident import Incident
    from app.im.application import Application
    from app.queue.queue import AsyncQueue


async def unfreeze_incident(incident: 'Incident', app: 'Application', queue: 'AsyncQueue'):
    if not incident.is_frozen():
        logger.info(f'Incident {incident.uuid} is not frozen, skipping unfreeze')
        return

    is_inhibition_unfreeze = incident.frozen_by_inhibition
    incident_status = incident.status
    incident.unfreeze()

    if not is_inhibition_unfreeze:
        _, header, _ = app.form_incident_message(incident)
        text_template = JinjaTemplate(notification_unfreeze)
        fields = {'type': app.type.value}
        text = text_template.form_notification(fields)
        if app.type.value == 'telegram':
            message = text
        else:
            message = header + '\n' + text
        await app.post_thread(incident.channel_id, incident.ts, message)
    
    await queue.put_first(datetime.now(timezone.utc), QueueItemType.STATUS_CHECK, incident.uniq_id)
    await queue.recreate(incident.status, incident.uniq_id, incident.get_chain(), incident.chain_active_seconds)
    if incident_status != 'deleted':
        await queue.put(incident.status_update_datetime, QueueItemType.UPDATE_STATUS, incident.uniq_id)
