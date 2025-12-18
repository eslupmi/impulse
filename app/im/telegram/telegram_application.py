import asyncio
from datetime import datetime

import aiohttp
from fastapi.responses import JSONResponse

from app.im.application import Application
from app.im.telegram.config import buttons
from app.im.telegram.user import User
from app.im.template import notification_freeze, notification_unfreeze
from app.jinja_template import JinjaTemplate
from app.logging import logger
from app.config.config import get_config
from app.config.environment import get_environment_config
from app.config.validation import ApplicationConfig
from app.time import calculate_freeze_time, format_freeze_expiration
from app.queue.queue import AsyncQueue
from app.queue.constants import QueueItemType
from app.incident.incident import Incident


class TelegramApplication(Application):
    icon_map = { #!
        '5312241539987020022': '🔥', # firing
        '5379748062124056162': '❗️', # unknown
        '5237699328843200968': '✅', # resolved
        '5408906741125490282': '🏁', # closed
        '5433614043006903194': '📆', # frozen 
    }

    def __init__(self, app_config: ApplicationConfig, channels, users):
        super().__init__(app_config, channels, users)

    def _initialize_specific_params(self):
        self.url += get_config().telegram_bot_token
        self.post_message_url = self.url + '/sendMessage'
        self.headers = {'Content-Type': 'application/json'}
        self.rate_limit = 20
        self.rate_window = 60.0
        self.thread_id_key = 'message_id'

    async def initialize_async(self):
        """Initialize async components after object creation"""
        await super().initialize_async()
        await self._setup_webhook()

    def _get_url(self, app_config: ApplicationConfig):
        return 'https://api.telegram.org/bot'

    def _get_public_url(self, app_config: ApplicationConfig):
        return 'https://api.telegram.org/bot'

    def _get_team_name(self, app_config: ApplicationConfig):
        return None

    def get_notification_destinations(self):
        return self.admin_users

    def _format_tg_icon(self, icon):
        return f'{self.icon_map.get(icon)}'

    def get_admins_text(self): #!
        return ', '.join([f'@{a.id}' for a in self.admin_users])

    async def create_thread(self, channel_id, body, header, status_icons, status):
        topic_id = await self._create_topic(channel_id, header, status_icons)
        payload = self._create_thread_payload(channel_id, body, header, status_icons, status)
        payload['message_thread_id'] = topic_id
        message_id = await self._send_create_thread(payload)
        return f'{topic_id}/{message_id}'

    async def _send_create_thread(self, payload):
        response = await self.http.post(self.post_message_url, headers=self.headers, json=payload)
        response_json = await response.json()
        response.close()
        return response_json.get('result', {}).get(self.thread_id_key)

    async def _handle_chain_action(self, action, incident_, user_id, user_display_name, queue_, incidents, payload):
        """Handle chain-related button actions (start_chain/stop_chain)"""
        await queue_.delete_by_id(incident_.uniq_id, delete_steps=True, delete_status=False)
        if action == 'stop_chain':
            if incident_.assigned_user_id == user_id:
                logger.info(f'Incident {incident_.uuid} -> button TAKE IT pressed, but user is already assigned')
                return JSONResponse(payload, status_code=200)
            logger.info(f'Incident {incident_.uuid} -> button TAKE IT pressed, assigning to {user_id}')
            incident_.assign_user_id(user_id)
            incident_.assign_user(user_display_name)
            self._track_async_task(asyncio.create_task(self.post_assignment_notification(incident_, user_id, user_display_name)))
            self._track_async_task(asyncio.create_task(self.fetch_and_assign_user_name(incident_, user_id, incidents)))
            incident_.chain_enabled = False
        else:
            logger.info(f'Incident {incident_.uuid} -> button RELEASE pressed')
            self._track_async_task(asyncio.create_task(self.post_unassignment_notification(incident_)))
            incident_.release()
        return None

    async def _handle_freeze_action(self, incident_: Incident, freeze_option: str, user_id: str, incidents, queue_: AsyncQueue, user_display_name: str = None, user_timezone: str = None):
        """Handle freeze button action"""
        config = get_config()
        telegram_tz = user_timezone or config.messenger.timezone
        freeze_time = calculate_freeze_time(freeze_option, config.app.general, telegram_tz)

        incident_.assign_user_id(user_id)
        incident_.assign_user(user_display_name)
        await self.fetch_and_assign_user_name(incident_, user_id, incidents, dump=False)
        incident_.freeze(freeze_time, user_id, user_display_name)
        
        logger.info(f'Incident {incident_.uuid} -> FREEZE with option {freeze_option}, frozen until {freeze_time} (timezone: {telegram_tz})')
        
        await queue_.delete_by_id(incident_.uniq_id, delete_steps=True, delete_status=False)
        await queue_.put(freeze_time, QueueItemType.UNFREEZE, incident_.uniq_id)
        self._track_async_task(asyncio.create_task(self._post_freeze_notification(incident_, freeze_time, telegram_tz)))

    async def _post_freeze_notification(self, incident_: Incident, freeze_time: datetime, telegram_tz: str = "UTC"):
        """Post freeze notification to thread"""
        text_template = JinjaTemplate(notification_freeze)
        fields = {'type': self.type.value, 'frozen_until': format_freeze_expiration(freeze_time, telegram_tz)}
        text = text_template.form_notification(fields)
        await self.post_thread(incident_.channel_id, incident_.ts, text)

    async def _post_unfreeze_notification(self, incident_: Incident):
        """Post unfreeze notification to thread"""
        text_template = JinjaTemplate(notification_unfreeze)
        text = text_template.form_notification({'type': self.type.value})
        await self.post_thread(incident_.channel_id, incident_.ts, text)

    async def _show_freeze_menu(self, incident_: Incident, callback):
        """Display freeze options menu"""
        body = self.body_template.form_message(incident_.payload, incident_)
        header = self.header_template.form_message(incident_.payload, incident_)
        status_icons = self.status_icons_template.form_message(incident_.payload, incident_)
        payload = self.update_thread_payload(
            incident_.channel_id, incident_.ts, body, header, status_icons,
            incident_.status, incident_.chain_enabled, incident_.frozen_until, 
            incident_.task_link, show_freeze_menu=True
        )
        await self._update_thread(incident_.ts, payload)
        await self.http.post(
            f'{self.url}/answerCallbackQuery',
            json={'callback_query_id': callback['id']},
            headers=self.headers
        )
        return JSONResponse({}, status_code=200)

    async def buttons_handler(self, payload, incidents, queue_, route):
        if 'callback_query' not in payload:
            return JSONResponse({}, status_code=200)

        callback = payload['callback_query']
        message_id = callback['message']['message_id']
        post_id = callback['message']['message_thread_id']
        thread_id = f'{post_id}/{message_id}'
        incident_ = incidents.get_by_ts(ts=thread_id)

        if incident_ is None:
            await self.http.post(
                f'{self.url}/answerCallbackQuery',
                json={'callback_query_id': callback['id']},
                headers=self.headers
            )
            return JSONResponse({}, status_code=200)

        action = callback['data']
        user_id = callback['from']['id']
        user_from = callback.get('from', {})
        first_name = user_from.get('first_name', '').strip()
        last_name = user_from.get('last_name', '').strip()
        user_display_name = f"{first_name} {last_name}".strip() or user_from.get('username')
        is_freeze_action = action.startswith('freeze_')

        if incident_.is_frozen() and not is_freeze_action:
            logger.info(f'Incident {incident_.uuid} is frozen, blocking all button actions')
            await self.http.post(
                f'{self.url}/answerCallbackQuery',
                json={'callback_query_id': callback['id']},
                headers=self.headers
            )
            return JSONResponse({}, status_code=200)

        if action == 'freeze_menu':
            if incident_.is_frozen():
                await self._handle_unfreeze_action(incident_, queue_)
            else:
                return await self._show_freeze_menu(incident_, callback)
        elif is_freeze_action and action != 'freeze_menu' and action != 'freeze_back':
            freeze_option_map = {
                'freeze_tomorrow': 'tomorrow',
                'freeze_next_monday': 'next_monday',
                'freeze_month': 'month',
                'freeze_6months': '6months'
            }
            if action in freeze_option_map:
                await self._handle_freeze_action(incident_, freeze_option_map[action], user_id, incidents, queue_, user_display_name)
        elif action == 'freeze_back':
            pass

        if action in ['start_chain', 'stop_chain']:
            early_return = await self._handle_chain_action(action, incident_, user_id, user_display_name, queue_, incidents, payload)
            if early_return is not None:
                return early_return
        elif action == 'task':
            self._handle_task_action(incident_, queue_)

        incident_.dump()
        body = self.body_template.form_message(incident_.payload, incident_)
        header = self.header_template.form_message(incident_.payload, incident_)
        status_icons = self.status_icons_template.form_message(incident_.payload, incident_)
        await self.update_thread(
            incident_.channel_id, incident_.ts, incident_.status, body, header, status_icons,
            incident_.chain_enabled, incident_.frozen_until, incident_.task_link
        )

        await self.http.post(
            f'{self.url}/answerCallbackQuery',
            json={'callback_query_id': callback['id']},
            headers=self.headers
        )
        return JSONResponse({}, status_code=200)

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
            response_json = await response.json()
            response.close()
            return response_json.get('result', {}).get('message_thread_id')
        except aiohttp.ClientError as e:
            logger.error(f'Failed to create topic: {e}')
            raise e

    def _create_thread_payload(self, channel_id, body, header, status_icons, status):
        env_config = get_environment_config()
        config_obj = get_config()

        keyboard_row = [
            buttons['chain']['takeit'],
            buttons['freeze']['inactive']
        ]

        if config_obj.app.task_management and env_config.task_management_enabled:
            keyboard_row.append(buttons['task']['create'])

        return {
            'chat_id': channel_id,
            'text': f'{self._format_tg_icon(status_icons)} {header}\n{body}',
            'parse_mode': 'HTML',
            'reply_markup': {
                'inline_keyboard': [keyboard_row]
            }
        }

    def _post_thread_payload(self, channel_id, id_, text):
        topic_id, _ = id_.split('/')
        return {
            'chat_id': channel_id,
            'text': text,
            'message_thread_id': topic_id,
            'parse_mode': 'HTML'
        }

    async def update_thread(self, channel_id, id_, status, body, header, status_icons, chain_enabled=True,
                      frozen_until=None, task_link=''):
        # Update topic icon based on frozen status
        if frozen_until or status == 'closed':
            await self._update_topic(channel_id, id_, header, status_icons)
        else:
            await self._update_topic(channel_id, id_, header, status_icons)
        payload = self.update_thread_payload(channel_id, id_, body, header, status_icons, status, chain_enabled,
                                             frozen_until, task_link)
        await self._update_thread(id_, payload)

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
            logger.error(f'Failed to update topic: {e}')

    def update_thread_payload(self, channel_id, id_, body, header, status_icons, status, chain_enabled,
                              frozen_until, task_link='', show_freeze_menu=False):
        env_config = get_environment_config()
        config_obj = get_config()

        _, message_id = id_.split('/')

        if show_freeze_menu:
            keyboard = []
            for opt in buttons['freeze']['options']:
                if opt['callback_data'] != 'freeze_back':
                    keyboard.append([opt])
            keyboard.append([buttons['freeze']['options'][-1]])
        else:
            chain_button = buttons['chain']['takeit'] if chain_enabled and status != 'resolved' else buttons['chain']['release']
            
            if frozen_until:
                telegram_tz = config_obj.messenger.timezone
                freeze_text = format_freeze_expiration(frozen_until, telegram_tz)
                freeze_button = {'text': freeze_text, 'callback_data': 'freeze_menu'}
            else:
                freeze_button = buttons['freeze']['inactive']
            
            keyboard_row = [chain_button, freeze_button]

            if config_obj.app.task_management and env_config.task_management_enabled and not task_link:
                keyboard_row.append(buttons['task']['create'])

            keyboard = [keyboard_row]

        return {
            'chat_id': channel_id,
            'message_id': message_id,
            'text': f'{self._format_tg_icon(status_icons)} {header}\n{body}',
            'parse_mode': 'HTML',
            'reply_markup': {
                'inline_keyboard': keyboard
            }
        }

    async def _update_thread(self, id_, payload):
        try:
            response = await self.http.post(
                f'{self.url}/editMessageText',
                json=payload,
                headers=self.headers
            )
            response.close()
        except aiohttp.ClientError as e:
            logger.error(f'Failed to update thread: {e}')

    def _markdown_links_to_native_format(self, text):
        return text

    async def get_user_details(self, user_details):
        id_ = user_details.get('id')
        response = await self.http.get(f'{self.url}/getChat?chat_id={id_}', headers=self.headers)

        if response.status != 200:
            logger.debug(f'Failed to get user details for {id_}: HTTP {response.status}')
            response.close()
            return {'id': id_, 'exists': False, 'full_name': None, 'username': None}

        data = await response.json()
        response.close()

        if not data.get('ok'):
            logger.debug(f'Telegram API error for user {id_}: {data.get("description", "unknown error")}')
            return {'id': id_, 'exists': False, 'full_name': None, 'username': None}

        chat_data = data.get('result', {})
        first_name = chat_data.get('first_name', '').strip()
        last_name = chat_data.get('last_name', '').strip()
        full_name = f"{first_name} {last_name}".strip()
        return {'id': id_, 'exists': True, 'full_name': full_name, 'username': full_name}

    def create_user(self, name, user_details):
        return User(
            name=name,
            id_=user_details.get('id'),
            exists=user_details.get('exists', False)
        )

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
            logger.error(f'Failed to set webhook: {e}')
            raise e
