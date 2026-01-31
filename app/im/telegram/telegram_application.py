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

    def _initialize_specific_params(self):
        env_config = get_environment_config()
        self.url += env_config.telegram_bot_token
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
        return ', '.join([f'@{a.get_notification_identifier()}' for a in self.admin_users])

    def _should_include_header_in_notifications(self) -> bool:
        """Telegram doesn't include header in freeze/unfreeze notifications"""
        return False

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

    async def _handle_chain_action(self, action, incident_, user_id, user_display_name, queue_, payload):
        """Handle chain-related button actions (start_chain/stop_chain)"""
        await queue_.delete_by_id(incident_.uniq_id, delete_steps=True, delete_status=False)
        if action == 'stop_chain':
            if incident_.assigned_user_id == user_id:
                logger.info('Button TAKE IT: user already assigned', extra={'uuid': incident_.uuid, 'user': user_id})
                return JSONResponse(payload, status_code=200)
            logger.info('Button TAKE IT: assigning to user', extra={'uuid': incident_.uuid, 'user': user_id})
            incident_.assign_user_id(user_id)
            incident_.assign_user(user_display_name)
            self._track_async_task(asyncio.create_task(self.post_assignment_notification(incident_, user_id, user_display_name)))
            self._track_async_task(asyncio.create_task(self.fetch_and_assign_user_name(incident_, user_id)))
            incident_.chain_enabled = False
        else:
            logger.info('Button pressed', extra={'uuid': incident_.uuid, 'button': 'release', 'user_id': user_id})
            self._track_async_task(asyncio.create_task(self.post_unassignment_notification(incident_)))
            incident_.release()
        return None

    async def _show_freeze_menu(self, incident_: 'Incident', callback):
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

    async def _answer_callback(self, callback_id):
        """Answer callback query to Telegram"""
        await self.http.post(
            f'{self.url}/answerCallbackQuery',
            json={'callback_query_id': callback_id},
            headers=self.headers
        )

    def _extract_user_display_name(self, user_from):
        """Extract user display name from callback user data"""
        first_name = user_from.get('first_name', '').strip()
        last_name = user_from.get('last_name', '').strip()
        return f"{first_name} {last_name}".strip() or user_from.get('username')

    async def _handle_freeze_actions(self, action, incident_, user_id, user_display_name, incidents, queue_, callback):
        """Handle all freeze-related actions"""
        if action == 'freeze_menu':
            if incident_.is_frozen():
                await self._handle_unfreeze_action(incident_, user_id, queue_)
            else:
                return await self._show_freeze_menu(incident_, callback)
            return None
        
        # freeze_back action closes the freeze menu, no additional processing needed
        if action == 'freeze_back':
            return None
        
        freeze_option_map = {
            'freeze_tomorrow': 'tomorrow',
            'freeze_next_monday': 'next_monday',
            'freeze_month': 'month',
            'freeze_6months': '6months'
        }
        
        if action in freeze_option_map:
            await self._handle_freeze_action(incident_, freeze_option_map[action], user_id, incidents, queue_, user_display_name)
        
        return None

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
        user_from = callback.get('from', {})
        first_name = user_from.get('first_name', '').strip()
        last_name = user_from.get('last_name', '').strip()
        fallback_name = f"{first_name} {last_name}".strip() or user_from.get('username')
        user_display_name = self.get_configured_user_name(user_id, fallback_name)
        
        # Check if this is a freeze action
        is_freeze_action = action.startswith('freeze_')

        # Block non-freeze actions if incident is frozen
        if incident_.is_frozen() and not is_freeze_action:
            logger.debug('Incident frozen, blocking actions', extra={'incident': incident_.uuid})
            await self._answer_callback(callback['id'])
            return JSONResponse({}, status_code=200)

        # Handle freeze actions
        if is_freeze_action:
            result = await self._handle_freeze_actions(action, incident_, user_id, user_display_name, incidents, queue_, callback)
            if result is not None:
                return result

        if action in ['start_chain', 'stop_chain']:
            early_return = await self._handle_chain_action(action, incident_, user_id, user_display_name, queue_, payload)
            if early_return is not None:
                return early_return
        elif action == 'task':
            self._handle_task_action(incident_, user_id, queue_)

        incident_.dump()
        body = self.body_template.form_message(incident_.payload, incident_)
        header = self.header_template.form_message(incident_.payload, incident_)
        status_icons = self.status_icons_template.form_message(incident_.payload, incident_)
        await self.update_thread(
            incident_.channel_id, incident_.ts, incident_.status, body, header, status_icons,
            incident_.chain_enabled, incident_.frozen_until, incident_.task_link
        )

        await self._answer_callback(callback['id'])
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
            logger.error("Topic creation failed", extra={'error': str(e)})
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
                      frozen_until=None, task_link='', frozen_by_inhibition=False):
        await self._update_topic(channel_id, id_, header, status_icons)
        payload = self.update_thread_payload(channel_id, id_, body, header, status_icons, status, chain_enabled,
                                             frozen_until, task_link, frozen_by_inhibition=frozen_by_inhibition)
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
            logger.error("Topic update failed", extra={'error': str(e)})

    def _build_freeze_menu_keyboard(self):
        """Build keyboard for freeze menu"""
        keyboard = []
        for opt in buttons['freeze']['options']:
            if opt['callback_data'] != 'freeze_back':
                keyboard.append([opt])
        keyboard.append([buttons['freeze']['options'][-1]])
        return keyboard

    def _build_main_keyboard(self, status, chain_enabled, frozen_until, task_link, frozen_by_inhibition=False):
        """Build main keyboard with chain, freeze, and task buttons"""
        config_obj = get_config()
        env_config = get_environment_config()
        
        chain_button = buttons['chain']['takeit'] if chain_enabled or status != 'resolved' else buttons['chain']['release']
        
        if frozen_by_inhibition:
            freeze_button = buttons['freeze']['inhibited']
        elif frozen_until:
            telegram_tz = config_obj.app.general.timezone
            freeze_text = format_freeze_expiration(frozen_until, telegram_tz)
            freeze_button = {'text': freeze_text, 'callback_data': 'freeze_menu'}
        else:
            freeze_button = buttons['freeze']['inactive']
        
        keyboard_row = [chain_button, freeze_button]

        if config_obj.app.task_management and env_config.task_management_enabled and not task_link:
            keyboard_row.append(buttons['task']['create'])

        return [keyboard_row]

    def update_thread_payload(self, channel_id, id_, body, header, status_icons, status, chain_enabled,
                              frozen_until, task_link='', show_freeze_menu=False, frozen_by_inhibition=False):
        _, message_id = id_.split('/')

        keyboard = self._build_freeze_menu_keyboard() if show_freeze_menu else self._build_main_keyboard(status, chain_enabled, frozen_until, task_link, frozen_by_inhibition)

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
            logger.error("Thread update failed", extra={'error': str(e)})

    def _markdown_links_to_native_format(self, text):
        return text

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
            'username': chat_data.get('username') or full_name,
            'first_name': first_name or None,
            'last_name': last_name or None,
            'email': None,
            'timezone': None,
        }

    def create_user(self, name, user_details):
        return User(
            name=name,
            id_=user_details.get('id'),
            exists=user_details.get('exists', False)
        )

    async def _generate_groups(self, groups_dict):
        """Telegram doesn't support groups, return empty dict"""
        return {}

    async def get_all_groups(self):
        """Telegram doesn't support groups, return empty dict"""
        return {}

    def create_group(self, config_name, group_details):
        """Telegram doesn't support groups, return None"""
        return None

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
