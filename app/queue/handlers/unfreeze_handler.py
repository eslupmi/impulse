from datetime import datetime, timezone

from app.im.template import notification_unfreeze
from app.jinja_template import JinjaTemplate
from app.logging import logger
from app.queue.constants import QueueItemType
from app.queue.handlers.base_handler import BaseHandler


class UnfreezeHandler(BaseHandler):
    """
    Handle unfreeze events when freeze duration expires.
    Delegates status-based cleanup to StatusCheckHandler.
    """
    __slots__ = []

    async def handle(self, uniq_id: str):
        """
        Handle unfreeze for an incident
        
        :param uniq_id: Incident unique ID
        """
        incident = self.incidents.uniq_ids.get(uniq_id)
        if incident is None:
            logger.warning(f'Incident with uniq_id {uniq_id} not found for unfreeze')
            return

        if not incident.is_frozen():
            logger.info(f'Incident {incident.uuid} is not frozen, skipping unfreeze')
            return

        is_inhibition_unfreeze = incident.frozen_by_inhibition
        has_thread = bool(incident.ts)
        incident_status = incident.status
        self.incidents.unfreeze_incident(uniq_id)
        
        if not has_thread:
            logger.debug("Incident has no thread, skipping all messenger operations", extra={'uuid': incident.uuid})
            await self.queue.put_first(datetime.now(timezone.utc), QueueItemType.STATUS_CHECK, uniq_id)
            if incident_status != 'deleted':
                await self.queue.put(incident.status_update_datetime, QueueItemType.UPDATE_STATUS, uniq_id)
            return
        
        if not is_inhibition_unfreeze:
            header = self.app.header_template.form_message(incident.payload, incident)
            text_template = JinjaTemplate(notification_unfreeze)
            fields = {'type': self.app.type.value}
            text = text_template.form_notification(fields)
            if self.app.type.value == 'telegram':
                message = text
            else:
                message = header + '\n' + text
            await self.app.post_thread(incident.channel_id, incident.ts, message)
        
        await self.queue.put_first(datetime.now(timezone.utc), QueueItemType.STATUS_CHECK, uniq_id)
        
        if incident_status != 'deleted':
            await self.queue.recreate(incident.status, uniq_id, incident.get_chain(), incident.chain_active_seconds)
            await self.queue.put(incident.status_update_datetime, QueueItemType.UPDATE_STATUS, uniq_id)
        
        body = self.app.body_template.form_message(incident.payload, incident)
        header = self.app.header_template.form_message(incident.payload, incident)
        status_icons = self.app.status_icons_template.form_message(incident.payload, incident)
        await self.app.update_thread(
            incident.channel_id, incident.ts, incident.status, body, header, status_icons,
            incident.chain_enabled, incident.frozen_until, incident.task_link
        )
