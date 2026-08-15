from app.config.validation import MessengerType
from app.im.template import chain_step_webhook, chain_template_context
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
    __slots__ = ['application', 'incidents', 'queue', 'webhooks']

    def __init__(self, queue, application, incidents, webhooks):
        super().__init__(queue, application, incidents)
        self.webhooks = webhooks

    async def handle(self, uniq_id, identifier):
        incident = self.incidents.uniq_ids[uniq_id]

        if incident.is_frozen:
            logger.debug("Incident frozen, skipping chain step", extra={'uniq_id': incident.uniq_id})
            return

        if not incident.ts:
            logger.debug("Incident has no thread, skipping chain step", extra={'uniq_id': incident.uniq_id})
            return

        step = incident.chain_steps[identifier]
        if step['name'] == 'webhook':
            webhook_name = step['value']
            webhook = self.webhooks.get(webhook_name)

            if webhook is not None:
                result, r_code = await webhook.push(incident)
                incident.chain_update(identifier, done=True, result=r_code, status=result)
                if result == 'ok':
                    logger.info("Webhook sent", extra={'uniq_id': incident.uniq_id, 'webhook': webhook_name, 'response': r_code})
                else:
                    logger.warning("Webhook failed", extra={'uniq_id': incident.uniq_id, 'webhook': webhook_name, 'response': r_code})
            else:
                incident.chain_update(identifier, done=True, result=None)
                logger.warning("Webhook undefined", extra={'uniq_id': incident.uniq_id, 'webhook': webhook_name})

            text = JinjaTemplate(chain_step_webhook[self.app.type.value]).form_notification(
                **chain_template_context(self.app, incident, step)
            )
            if self.app.type == MessengerType.TELEGRAM:
                message = text
            else:
                header = self.app.header_template.form_message(incident.payload, incident)
                message = header + '\n' + text
            await self.app.post_to_thread(incident.channel_id, incident.ts, message)
        else:
            r_code = await self.app.notify(incident, step)
            incident.chain_update(identifier, done=True, result=r_code)
