import asyncio
from typing import TYPE_CHECKING

import aiohttp
from fastapi.responses import JSONResponse

from app.im.application import Application

if TYPE_CHECKING:
    from app.incident.incident import Incident
from app.im.telegram.config import buttons
from app.im.telegram.user import User
from app.logging import logger
from app.config.config import get_config
from app.config.environment import get_environment_config
from app.config.validation import ApplicationConfig
from app.time import format_freeze_expiration


class TelegramApplication(Application):
    icon_map = { #!
        '5312241539987020022': '🔥', # firing
        '5379748062124056162': '❗️', # unknown
        '5237699328843200968': '✅', # resolved
        '5408906741125490282': '🏁', # closed
        '5309958691854754293': '💎', # frozen 
    }

    def __init__(self, app_config: ApplicationConfig, channels, users):
        super().__init__(app_config, channels, users)

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

        if incident_.is_frozen() and not is_freeze_action:
            logger.debug('Incident frozen, blocking actions', extra={'incident': incident_.uuid})
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

    async def create_incident_message(self, incident, body, header, status_icons):
        topic_id = await self._create_topic(incident.channel_id, header, status_icons)
        if topic_id is None:
            return None
        payload = self._get_incident_message_payload(incident, body, header, status_icons)
        payload['message_thread_id'] = topic_id
        message_id = await self._send_create_incident_message(payload)
        if message_id is None:
            return None
        return f'{topic_id}/{message_id}'

    def create_group(self, config_name, group_details):
        return None

    def create_user(self, name, user_details):
        return User(
            name=name,
            id_=user_details.get('id'),
            exists=user_details.get('exists', False),
            full_name=user_details.get('full_name')
        )

    async def get_all_groups(self):
        return {}

    def get_notification_destinations(self):
        return self.admin_users

    async def get_user_details(self, user_details):
        id_ = user_details.get('id')
        response = await self.http.get(f'{self.url}/getChat?chat_id={id_}', headers=self.headers)
        if response.status != 200:
            logger.debug("User details fetch failed", extra={'user_id': id_, 'status': response.status})
            response.close()
            return {'id': id_, 'exists': False, 'full_name': None, 'username': None,
                    'first_name': None, 'last_name': None, 'email': None, 'timezone': None}

        data = await response.json()
        response.close()

        if not data.get('ok'):
            logger.debug("Telegram API error",
                         extra={'user_id': id_, 'error': data.get("description", "unknown error")})
            return {'id': id_, 'exists': False, 'full_name': None, 'username': None,
                    'first_name': None, 'last_name': None, 'email': None, 'timezone': None}

        chat_data = data.get('result', {})
        first_name = chat_data.get('first_name', '').strip()
        last_name = chat_data.get('last_name', '').strip()
        full_name = f"{first_name} {last_name}".strip()
        return {
            'id': id_,
            'exists': True,
            'full_name': full_name,
            'username': chat_data.get('username'),
            'email': None,
            'timezone': None,
        }

    async def initialize_async(self):
        await super().initialize_async()
        await self._setup_webhook()

    async def update_incident_message(self, incident):
        body, header, status_icons = self.form_body_header_status_icons(incident)

        await self._update_topic(incident.channel_id, incident.ts, header, status_icons)
        payload = self.update_incident_payload(incident, body, header, status_icons, show_freeze_menu=False)
        await self._update_incident_message(incident.ts, payload)

    def update_incident_payload(self, incident, body, header, status_icons, show_freeze_menu = False):
        _, message_id = incident.ts.split('/')
        if show_freeze_menu:
            keyboard = self._build_freeze_menu_keyboard()
        else:
            keyboard = self._build_main_keyboard(incident)
        payload = {
            'chat_id': incident.channel_id,
            'message_id': message_id,
            'text': f'{self._format_tg_icon(status_icons)} {header}\n{body}',
            'parse_mode': 'HTML',
        }
        payload['reply_markup'] = {'inline_keyboard': keyboard}
        return payload

    ### PRIVATE METHODS ###

    async def _answer_callback(self, callback_id):
        await self.http.post(
            f'{self.url}/answerCallbackQuery',
            json={'callback_query_id': callback_id},
            headers=self.headers
        )

    @staticmethod
    def _build_freeze_menu_keyboard():
        keyboard = []
        for opt in buttons['freeze']['options']:
            if opt['callback_data'] != 'freeze_back':
                keyboard.append([opt])
        keyboard.append([buttons['freeze']['options'][-1]])
        return keyboard

    @staticmethod
    def _build_main_keyboard(incident):
        if incident.status == 'closed':
            return []

        config_obj = get_config()
        env_config = get_environment_config()

        if incident.chain_enabled:
            chain_button = buttons['chain']['takeit']
        else:
            if incident.status == 'resolved':
                chain_button = buttons['chain']['release']
            else:
                chain_button = buttons['chain']['assigned']

        if incident.frozen_by_inhibition:
            freeze_button = buttons['freeze']['inhibited']
        elif incident.frozen_until:
            telegram_tz = config_obj.app.general.timezone
            freeze_text = format_freeze_expiration(incident.frozen_until, telegram_tz)
            freeze_button = {'text': freeze_text, 'callback_data': 'freeze_menu'}
        else:
            freeze_button = buttons['freeze']['inactive']
        
        keyboard_row = [chain_button, freeze_button]

        if config_obj.app.task_management and env_config.task_management_enabled and not incident.task_link:
            keyboard_row.append(buttons['task']['create'])

        return [keyboard_row]

    async def _create_topic(self, channel_id, header, status_icons):
        payload = {
            'chat_id': channel_id,
            'name': header,
            'icon_custom_emoji_id': status_icons
        }
        try:
            response = await self.http.post(
                f'{self.url}/createForumTopic',
                json=payload,
                headers=self.headers
            )
            status = response.status
            response_json = await response.json()
            response.close()
            if status != 200 or response_json.get('ok') is not True:
                logger.warning(
                    "Telegram topic creation failed",
                    extra={
                        'channel_id': channel_id,
                        'status': status,
                        'description': response_json.get('description'),
                    },
                )
                return None
            return response_json.get('result', {}).get('message_thread_id')
        except aiohttp.ClientError as e:
            logger.error("Topic creation failed", extra={'error': str(e)})
            raise e

    def _format_tg_icon(self, icon):
        return f'{self.icon_map.get(icon)}'

    async def _generate_groups(self, groups_dict):
        return {}

    def _get_incident_message_payload(self, incident, body, header, status_icons):
        env_config = get_environment_config()
        config_obj = get_config()

        keyboard_row = []
        if incident.status != 'closed':
            freeze_button = buttons['freeze']['inhibited'] if incident.frozen_by_inhibition else buttons['freeze']['inactive']
            keyboard_row = [
                buttons['chain']['takeit'],
                freeze_button
            ]

            if config_obj.app.task_management and env_config.task_management_enabled:
                keyboard_row.append(buttons['task']['create'])

        return {
            'chat_id': incident.channel_id,
            'text': f'{self._format_tg_icon(status_icons)} {header}\n{body}',
            'parse_mode': 'HTML',
            'reply_markup': {
                'inline_keyboard': [keyboard_row] if keyboard_row else []
            }
        }

    def _get_public_url(self, app_config: ApplicationConfig):
        return 'https://api.telegram.org/bot'

    def _get_team_name(self, app_config: ApplicationConfig):
        return None

    def _get_url(self, app_config: ApplicationConfig):
        return 'https://api.telegram.org/bot'

    async def _handle_chain_action(self, action, incident_, user_id, queue_, payload):
        await queue_.delete_by_id(incident_.uniq_id, delete_steps=True, delete_status=False)
        if action == 'stop_chain':
            if incident_.assigned_user_id == user_id:
                logger.info('Button TAKE IT: user already assigned', extra={'uuid': incident_.uuid, 'user_id': user_id})
                return JSONResponse(payload, status_code=200)
            logger.info('Button TAKE IT: assigning to user', extra={'uuid': incident_.uuid, 'user_id': user_id})
            self.fetch_and_assign_user_name(incident_, user_id, dump=False)
            self.track_async_task(asyncio.create_task(self.post_assignment_notification(incident_)))
            incident_.chain_enabled = False
        else:
            logger.info('Button pressed', extra={'uuid': incident_.uuid, 'button': 'release', 'user_id': user_id})
            self.track_async_task(asyncio.create_task(self.post_unassignment_notification(incident_)))
            incident_.release()
        return None

    async def _handle_freeze_actions(self, action, incident_, user_id, incidents, queue_, callback):
        if action == 'freeze_menu':
            if incident_.is_frozen():
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

    def _initialize_specific_params(self):
        env_config = get_environment_config()
        self.url += env_config.telegram_bot_token
        self.post_message_url = self.url + '/sendMessage'
        self.headers = {'Content-Type': 'application/json'}
        self.rate_limit = 20
        self.rate_window = 60.0
        self.thread_id_key = 'message_id'

    def _markdown_links_to_native_format(self, text):
        return text

    def _post_thread_payload(self, channel_id, id_, text):
        topic_id, _ = id_.split('/')
        return {
            'chat_id': channel_id,
            'text': text,
            'message_thread_id': topic_id,
            'parse_mode': 'HTML'
        }

    async def _send_create_incident_message(self, payload):
        logger.debug('Create incident message')
        response = await self.http.post(self.post_message_url, headers=self.headers, json=payload)
        status = response.status
        response_json = await response.json()
        response.close()
        if status != 200 or response_json.get('ok') is not True:
            logger.warning(
                "Telegram incident message creation failed",
                extra={
                    'channel_id': payload.get('chat_id'),
                    'status': status,
                    'description': response_json.get('description'),
                },
            )
            return None
        return response_json.get('result', {}).get(self.thread_id_key)

    async def _setup_webhook(self):
        config = get_config()
        try:
            response = await self.http.post(
                f'{self.url}/setWebhook',
                params={'url': f"{config.messenger.impulse_address}/app"},
                headers=self.headers
            )
            response.close()
        except aiohttp.ClientError as e:
            logger.error("Webhook setup failed", extra={'error': str(e)})
            raise e

    async def _show_freeze_menu(self, incident_: 'Incident', callback):
        body, header, status_icons = self.form_body_header_status_icons(incident_)
        payload = self.update_incident_payload(incident_, body, header, status_icons, show_freeze_menu=True)
        await self._update_incident_message(incident_.ts, payload)
        await self.http.post(
            f'{self.url}/answerCallbackQuery',
            json={'callback_query_id': callback['id']},
            headers=self.headers
        )
        return JSONResponse({}, status_code=200)

    async def _update_incident_message(self, id_, payload):
        try:
            response = await self.http.post(
                f'{self.url}/editMessageText',
                json=payload,
                headers=self.headers
            )
            response.close()
        except aiohttp.ClientError as e:
            logger.error("Thread update failed", extra={'error': str(e)})

    async def _update_topic(self, channel_id, id_, header, status_icons):
        topic_id, _ = id_.split('/')
        payload = {
            'chat_id': channel_id,
            'name': header,
            'icon_custom_emoji_id': status_icons,
            'message_thread_id': topic_id
        }
        try:
            response = await self.http.post(
                f'{self.url}/editForumTopic',
                json=payload,
                headers=self.headers
            )
            response.close()
        except aiohttp.ClientError as e:
            logger.error("Topic update failed", extra={'error': str(e)})
