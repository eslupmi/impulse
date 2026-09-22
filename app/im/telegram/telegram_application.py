import asyncio
from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse

from app.im.application import Application
from app.im.messenger_init import messenger_init_step_async

if TYPE_CHECKING:
    from app.incident.incident import Incident
from app.config.validation import ApplicationConfig
from app.im.telegram.user import User
from app.logging import logger


from app.im.providers.telegram import TelegramProvider


class TelegramApplication(TelegramProvider, Application):
    """Legacy callback/user adapter; startup uses the composed Application."""

    def __init__(self, app_config: ApplicationConfig, channels, users, webhooks=None):
        Application.__init__(self, app_config, channels, users, webhooks=webhooks)

    async def buttons_handler(self, payload, incidents, queue_, route):
        if 'callback_query' not in payload:
            return JSONResponse({}, status_code=200)

        callback = payload['callback_query']
        message_id = callback['message']['message_id']
        post_id = callback['message']['message_thread_id']
        thread_id = f'{post_id}/{message_id}'
        incident_ = incidents.get_by_ts(ts=thread_id)

        if incident_ is None:
            await self._answer_callback(callback['id'])
            return JSONResponse({}, status_code=200)

        action = callback['data']
        user_id = callback['from']['id']

        is_freeze_action = action.startswith('freeze_')

        if incident_.is_frozen and not is_freeze_action:
            logger.debug('Incident frozen, blocking actions', extra={'incident': incident_.uniq_id})
            await self._answer_callback(callback['id'])
            return JSONResponse({}, status_code=200)

        if is_freeze_action:
            result = await self._handle_freeze_actions(action, incident_, user_id, incidents, queue_, callback)
            if result is not None:
                return result

        if action in ['start_chain', 'stop_chain']:
            early_return = await self._handle_chain_action(action, incident_, user_id, queue_, payload)
            if early_return is not None:
                return early_return
        elif action == 'task':
            self._handle_task_action(incident_, user_id, queue_)

        incident_.dump()
        await self.update_incident_message(incident_)

        await self._answer_callback(callback['id'])
        return JSONResponse({}, status_code=200)

    def create_group(self, config_name, group_details):
        return None

    def create_user(self, name, user_details):
        return User(
            name=name,
            id_=user_details.get('id'),
            exists=user_details.get('exists', False),
            full_name=user_details.get('full_name'),
            username=user_details.get('username'),
        )

    def get_notification_destinations(self):
        return self.admin_users

    async def initialize_async(self):
        await super().initialize_async()
        await self._init_webhook()

    @messenger_init_step_async('webhook')
    async def _init_webhook(self):
        await self._setup_webhook()

    async def _generate_groups(self, groups_dict):
        return {}

    async def _handle_chain_action(self, action, incident_, user_id, queue_, payload):
        await queue_.delete_by_id(incident_.uniq_id, delete_steps=True, delete_status=False)
        if action == 'stop_chain':
            if incident_.assigned_user_id == user_id:
                logger.info('Button TAKE IT: user already assigned', extra={'uniq_id': incident_.uniq_id, 'user_id': user_id})
                return JSONResponse(payload, status_code=200)
            logger.info('Button TAKE IT: assigning to user', extra={'uniq_id': incident_.uniq_id, 'user_id': user_id})
            self.fetch_and_assign_user_name(incident_, user_id, dump=False)
            self.track_async_task(asyncio.create_task(self.post_assignment_notification(incident_)))
            incident_.chain_enabled = False
        else:
            logger.info('Button pressed', extra={'uniq_id': incident_.uniq_id, 'button': 'release', 'user_id': user_id})
            self.track_async_task(asyncio.create_task(self.post_unassignment_notification(incident_)))
            incident_.release()
        return None

    async def _handle_freeze_actions(self, action, incident_, user_id, incidents, queue_, callback):
        if action == 'freeze_menu':
            if incident_.can_manual_unfreeze():
                await self._handle_unfreeze_action(incident_, user_id, queue_)
            else:
                return await self._show_freeze_menu(incident_, callback)
            return None

        if action == 'freeze_back':
            return None

        freeze_option_map = {
            'freeze_tomorrow': 'tomorrow',
            'freeze_next_monday': 'next_monday',
            'freeze_month': 'month',
            'freeze_6months': '6months'
        }

        if action in freeze_option_map:
            await self._handle_freeze_action(incident_, freeze_option_map[action], user_id, incidents, queue_)

        return None

    async def _show_freeze_menu(self, incident_: 'Incident', callback):
        body, header, status_icons = self.form_body_header_status_icons(incident_)
        payload = self.update_incident_payload(incident_, body, header, status_icons, show_freeze_menu=True)
        await self._update_incident_message(incident_.ts, payload)
        await self._answer_callback(callback['id'])
        return JSONResponse({}, status_code=200)

    async def update_incident_message(self, incident):
        body, header, status_icons = self.form_body_header_status_icons(incident)
        await self._update_topic(incident.channel_id, incident.ts, header, status_icons)
        payload = self.update_incident_payload(incident, body, header, status_icons, show_freeze_menu=False)
        await self._update_incident_message(incident.ts, payload)
