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
            webhook_name = step['identifier']
            webhook = self.webhooks.get(webhook_name)

            text_template = JinjaTemplate(notification_webhook)
            admins = self.app.get_notification_destinations()

            if webhook is not None:
                # Pass the app's HTTP session to the webhook if available
                if hasattr(self.app, 'http') and self.app.http:
                    result, r_code = await webhook.push(incident, session=self.app.http)
                else:
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
            header = f"{self.app.format_text_italic(self.app.header_template.form_message(incident.last_state, incident))}"
            message = f"{header}" + '\n' + f'{text}'
            # For Telegram we use thread_id (topic_id/message_id) for sending messages
            # For other applications we use ts
            thread_identifier = incident.thread_id if incident.thread_id else incident.ts
            await self.app.post_thread(incident.channel_id, thread_identifier, message)
        else:
            r_code = await self.app.notify(incident, step['type'], step['identifier'])
            incident.chain_update(identifier, done=True, result=r_code)
