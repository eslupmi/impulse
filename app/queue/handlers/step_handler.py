from app.im.template import JinjaTemplate, notification_webhook
from app.logging import logger
from app.queue.handlers.base_handler import BaseHandler


class StepHandler(BaseHandler):
    """
    StepHandler class is responsible for handling the step event.

    :param queue: AsyncQueue instance
    :param application: Application instance
    :param incidents: Incidents instance
    :param webhooks: Webhooks instance
    """
    __slots__ = ['queue', 'application', 'incidents', 'webhooks']

    def __init__(self, queue, application, incidents, webhooks):
        super().__init__(queue, application, incidents)
        self.webhooks = webhooks

    async def handle(self, uuid_, identifier):
        incident = self.incidents.by_uuid[uuid_]
        step = incident.chain[identifier]

        if step['type'] == 'webhook':
            webhook = self.webhooks[step['identifier']]
            status, status_code = webhook.push(incident)
            incident.chain_update(identifier, True, f'{status} {status_code}')
            logger.info(f'Incident {uuid_} -> webhook {step["identifier"]} executed with status {status}')

        elif step['type'] == 'notification':
            header = self.application.format_text_italic(
                self.application.header_template.form_message(incident.last_state, incident)
            )
            fields = {
                'type': self.application.type,
                'step': step['identifier'],
                'admins': self.application.get_notification_destinations()
            }
            text = JinjaTemplate(notification_webhook).form_notification(fields)
            if self.application.type == 'telegram':
                message = text
            else:
                message = header + '\n' + text
            self.application.post_thread(incident.channel_id, incident.ts, message)
            incident.chain_update(identifier, True, 'sent')
            logger.info(f'Incident {uuid_} -> notification {step["identifier"]} sent')

        elif step['type'] == 'sleep':
            incident.chain_update(identifier, True, 'done')
            logger.info(f'Incident {uuid_} -> sleep {step["identifier"]} done')
