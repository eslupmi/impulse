from typing import ClassVar

import aiohttp


from app.config.config import get_config
from app.config.environment import get_environment_config
from app.config.validation import ApplicationConfig
from app.im.telegram.config import buttons
from app.im.users import BaseUser
from app.logging import logger
from app.time import format_freeze_expiration


from app.im.providers.legacy import LegacyProviderAdapter
from app.im.plugin_api import ProviderDescriptor


class TelegramProvider(LegacyProviderAdapter):
    descriptor = ProviderDescriptor("telegram", rate_limit=20, rate_window_seconds=60.0)

    icon_map: ClassVar[dict[str, str]] = {
        '5312241539987020022': '🔥', # firing
        '5379748062124056162': '❗️', # unknown
        '5237699328843200968': '✅', # resolved
        '5408906741125490282': '🏁', # closed
        '5309958691854754293': '💎', # frozen
    }

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

    async def get_all_groups(self):
        return {}

    async def get_user_details(self, user_details):
        id_ = user_details.get('id')
        response = await self.http.get(f'{self.url}/getChat?chat_id={id_}', headers=self.headers)
        if response.status != 200:
            logger.debug("User details fetch failed", extra={'user_id': id_, 'status': response.status})
            response.close()
            return {'id': id_, 'exists': False, 'full_name': None, 'username': None,
                    'first_name': None, 'last_name': None, 'email': None, 'timezone': None}

        data = await self._read_response_json(response)

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

    async def _update_presentation(self, incident):
        body, header, status_icons = incident.body, incident.header, incident.status_icon

        await self._update_topic(incident.channel_id, incident.ts, header, status_icons)
        payload = self.update_incident_payload(incident, body, header, status_icons, show_freeze_menu=False)
        await self._update_incident_message(incident.ts, payload)

    def update_incident_payload(self, incident, body, header, status_icons, tz_str=None, **kwargs):
        show_freeze_menu = kwargs.get("show_freeze_menu", False)
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

    async def _answer_callback(self, callback_id):
        response = await self.http.post(
            f'{self.url}/answerCallbackQuery',
            json={'callback_query_id': callback_id},
            headers=self.headers
        )
        response.close()

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

        if incident.frozen_by_maintenance:
            freeze_button = {'text': 'Maintenance', 'callback_data': 'noop'}
        elif incident.frozen_by_inhibition:
            freeze_button = buttons['freeze']['inhibited']
        elif incident.can_manual_unfreeze():
            telegram_tz = config_obj.app.general.timezone
            freeze_text = format_freeze_expiration(incident.frozen_until, telegram_tz)
            freeze_button = {'text': freeze_text, 'callback_data': 'freeze_menu'}
        elif incident.frozen_until:
            telegram_tz = config_obj.app.general.timezone
            freeze_text = format_freeze_expiration(incident.frozen_until, telegram_tz)
            freeze_button = {'text': freeze_text, 'callback_data': 'noop'}
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
            response_json = await self._read_response_json(response)
            if status != 200 or response_json.get('ok') is not True:
                logger.error(
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
            raise

    def _format_tg_icon(self, icon):
        return f'{self.icon_map.get(icon)}'

    def _get_incident_message_payload(self, incident, body, header, status_icons):
        env_config = get_environment_config()
        config_obj = get_config()

        keyboard_row = []
        if incident.status != 'closed':
            if incident.frozen_by_maintenance:
                freeze_button = {'text': 'Maintenance', 'callback_data': 'noop'}
            elif incident.frozen_by_inhibition:
                freeze_button = buttons['freeze']['inhibited']
            else:
                freeze_button = buttons['freeze']['inactive']
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

    async def _get_public_url(self, app_config: ApplicationConfig):
        return 'https://api.telegram.org/bot'

    def _get_team_name(self, app_config: ApplicationConfig):
        return None

    def _get_url(self, app_config: ApplicationConfig):
        return get_environment_config().dev_messenger_custom_address or 'https://api.telegram.org/bot'

    def _build_user_profile_url(self, user_id: str, user: BaseUser) -> str | None:
        if not user.username:
            return None
        return f"https://t.me/{user.username}"

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
        response_json = await self._read_response_json(response)
        if status != 200 or response_json.get('ok') is not True:
            logger.error(
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
        response = await self.http.post(
            f'{self.url}/setWebhook',
            params={'url': f"{config.messenger.impulse_address}/app"},
            headers=self.headers
        )
        response.close()

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

    async def start(self):
        await self._setup_webhook()

    def notification_text(self, content):
        return content.text

    def user_url(self, user, identity):
        return f"https://t.me/{user.username}" if user.username else None
