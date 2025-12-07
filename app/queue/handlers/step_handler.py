from app.config.validation import MessengerType
from app.im.template import notification_webhook
from app.jinja_template import JinjaTemplate
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

    async def handle(self, uniq_id, identifier):
        incident = self.incidents.uniq_ids[uniq_id]
        step = incident.chain[identifier]
        if step['type'] == 'webhook':
            webhook_name = step['identifier']
            webhook = self.webhooks.get(webhook_name)

            text_template = JinjaTemplate(notification_webhook)
            admins = self.app.get_notification_destinations()

            if webhook is not None:
                result, r_code = await webhook.push(incident)
                fields = {'type': self.app.type, 'name': webhook_name, 'unit': webhook, 'admins': admins,
                          'result': result, 'response': r_code}
                incident.chain_update(identifier, done=True, result=r_code)
                if result == 'ok':
                    logger.info(f'Incident {incident.uuid} -> chain step webhook \'{webhook_name}\': {result}, '
                                f'response code {r_code}')
                else:
                    logger.warning(f'Incident {incident.uuid} -> chain step webhook \'{webhook_name}\': {result}, '
                                   f'response code {r_code}')
            else:
                fields = {'type': self.app.type, 'name': webhook_name, 'unit': webhook, 'admins': admins}

                incident.chain_update(identifier, done=True, result=None)
                logger.warning(
                    f'Incident {incident.uuid} -> chain step webhook \'{webhook_name}\': undefined in impulse.yml'
                )

            text = text_template.form_notification(fields)
            if self.app.type == MessengerType.TELEGRAM:
                message = text
            else:
                header = self.app.header_template.form_message(incident.payload, incident)
                message = header + '\n' + text
            await self.app.post_thread(incident.channel_id, incident.ts, message)
        else:
            r_code = await self.app.notify(incident, step['type'], step['identifier'])
            incident.chain_update(identifier, done=True, result=r_code)
