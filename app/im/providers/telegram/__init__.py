"""Telegram wire protocol, payloads and packaged templates."""
import json
import logging
from importlib.resources import files

from app.im.plugin_api import (
    DeliveryResult, GroupProfile, IncidentPresentation, Interaction, InteractionAction,
    InteractionCommand, InteractionRequest, MessageRef, NotificationContent, ProviderContext,
    ProviderDescriptor, ProviderIdentity, ProviderResponse, SecretResolver, UserProfile,
)
from .buttons import buttons
from .config import TelegramApplicationConfig

logger = logging.getLogger('main_logger')

API_BASE = 'https://api.telegram.org/bot'
ICON_MAP = {
    '5312241539987020022': '🔥', '5379748062124056162': '❗️',
    '5237699328843200968': '✅', '5408906741125490282': '🏁',
    '5309958691854754293': '💎',
}
FREEZE_OPTIONS = {
    'freeze_tomorrow': 'tomorrow', 'freeze_next_monday': 'next_monday',
    'freeze_month': 'month', 'freeze_6months': '6months',
}
TEMPLATE_NAMES = frozenset({
    'body', 'header', 'status_icons', 'chain_step_user', 'chain_step_user_group', 'chain_step_group',
    'chain_step_webhook', 'incident_notifications_assignment', 'incident_notifications_status_update',
    'incident_notifications_new_firing', 'incident_notifications_partial_resolved',
    'incident_notifications_freeze', 'incident_notifications_unfreeze',
})


class TelegramProvider:
    descriptor = ProviderDescriptor(
        'telegram', rate_limit=20, rate_window_seconds=60.0, user_update_gap_seconds=60.0,
        notification_headers=False, refresh_inhibition_source=False, html_autoescape=True,
        allow_inhibited_freeze_actions=True,
    )
    config_model = TelegramApplicationConfig

    def __init__(self, config: TelegramApplicationConfig, secrets: SecretResolver):
        token = secrets.get('TELEGRAM_BOT_TOKEN')
        if not token:
            raise ValueError('TELEGRAM_BOT_TOKEN is required')
        self._token = token
        self.url = (secrets.get('DEV_MESSENGER_CUSTOM_ADDRESS') or API_BASE).rstrip('/') + token
        self.team = None
        self.headers = {'Content-Type': 'application/json'}
        self.callback_url = f'{config.impulse_address}/app'
        self.http = None

    def redact_url(self, url: str) -> str:
        return url.replace(self._token, '***')

    async def initialize(self, context: ProviderContext) -> ProviderIdentity:
        self.http = context.http
        self.callback_url = context.callback_url
        return ProviderIdentity(API_BASE)

    async def activate(self) -> None:
        response = await self.http.post(f'{self.url}/setWebhook', params={'url': self.callback_url}, headers=self.headers)
        response.close()

    @staticmethod
    async def _read_json(response):
        try:
            return await response.json()
        finally:
            response.close()

    async def fetch_user(self, user_id: str | int) -> UserProfile:
        response = await self.http.get(f'{self.url}/getChat?chat_id={user_id}', headers=self.headers)
        status = response.status
        if status != 200:
            response.close()
            logger.debug('User details fetch failed', extra={'user_id': user_id, 'status': status})
            return UserProfile(id=user_id, exists=False)
        data = await self._read_json(response)
        if not data.get('ok'):
            logger.debug('Telegram API error', extra={'user_id': user_id, 'status': status})
            return UserProfile(id=user_id, exists=False)
        chat = data.get('result') or {}
        full_name = f"{(chat.get('first_name') or '').strip()} {(chat.get('last_name') or '').strip()}".strip()
        return UserProfile(id=user_id, exists=True, full_name=full_name, username=chat.get('username'))

    async def fetch_groups(self) -> tuple[GroupProfile, ...]:
        return ()

    @staticmethod
    def _text(message: IncidentPresentation) -> str:
        return f'{ICON_MAP.get(message.status_icon)} {message.header}\n{message.body}'

    @staticmethod
    def _freeze_button(message: IncidentPresentation, *, creating=False):
        if message.frozen_by_maintenance:
            return {'text': 'Maintenance', 'callback_data': 'noop'}
        if message.frozen_by_inhibition:
            return buttons['freeze']['inhibited']
        if creating:
            return buttons['freeze']['inactive']
        if message.can_unfreeze:
            return {'text': message.frozen_until_text, 'callback_data': 'freeze_menu'}
        if message.frozen_until:
            return {'text': message.frozen_until_text, 'callback_data': 'noop'}
        return buttons['freeze']['inactive']

    @classmethod
    def _keyboard(cls, message: IncidentPresentation, *, creating=False, freeze_menu=False):
        if freeze_menu:
            return [[option] for option in buttons['freeze']['options']]
        if message.status == 'closed':
            return []
        if creating or message.chain_enabled:
            chain = buttons['chain']['takeit']
        elif message.status == 'resolved':
            chain = buttons['chain']['release']
        else:
            chain = buttons['chain']['assigned']
        row = [chain, cls._freeze_button(message, creating=creating)]
        if message.can_create_task and (creating or not message.task_link):
            row.append(buttons['task']['create'])
        return [row]

    @classmethod
    def payload(cls, message: IncidentPresentation, *, creating=False, freeze_menu=False):
        body = {
            'chat_id': message.channel_id, 'text': cls._text(message), 'parse_mode': 'HTML',
            'reply_markup': {'inline_keyboard': cls._keyboard(message, creating=creating, freeze_menu=freeze_menu)},
        }
        if not creating:
            _, message_id = message.thread_id.split('/')
            body['message_id'] = message_id
        return body

    async def create_incident(self, message: IncidentPresentation) -> MessageRef | None:
        topic_payload = {
            'chat_id': message.channel_id, 'name': message.header, 'icon_custom_emoji_id': message.status_icon,
        }
        response = await self.http.post(
            f'{self.url}/createForumTopic', json=topic_payload, headers=self.headers)
        status = response.status
        data = await self._read_json(response)
        if status != 200 or data.get('ok') is not True:
            logger.error('Telegram topic creation failed', extra={
                'channel_id': message.channel_id, 'status': status,
            })
            return None
        topic_id = (data.get('result') or {}).get('message_thread_id')
        if topic_id is None:
            return None
        payload = self.payload(message, creating=True)
        payload['message_thread_id'] = topic_id
        response = await self.http.post(
            f'{self.url}/sendMessage', headers=self.headers, json=payload)
        status = response.status
        data = await self._read_json(response)
        if status != 200 or data.get('ok') is not True:
            logger.error('Telegram incident message creation failed', extra={
                'channel_id': message.channel_id, 'status': status,
            })
            return None
        message_id = (data.get('result') or {}).get('message_id')
        return MessageRef(message.channel_id, f'{topic_id}/{message_id}') if message_id is not None else None

    async def update_incident(self, message: IncidentPresentation) -> None:
        topic_id, _ = message.thread_id.split('/')
        response = await self.http.post(f'{self.url}/editForumTopic', json={
            'chat_id': message.channel_id, 'name': message.header,
            'icon_custom_emoji_id': message.status_icon, 'message_thread_id': topic_id,
        }, headers=self.headers)
        response.close()
        await self._edit_message(message)

    async def _edit_message(self, message: IncidentPresentation, *, freeze_menu=False):
        response = await self.http.post(f'{self.url}/editMessageText',
                                        json=self.payload(message, freeze_menu=freeze_menu), headers=self.headers)
        response.close()

    async def post_notification(self, message: MessageRef, content: NotificationContent) -> DeliveryResult:
        topic_id, _ = message.thread_id.split('/')
        response = await self.http.post(f'{self.url}/sendMessage', headers=self.headers, json={
            'chat_id': message.channel_id, 'text': content.text,
            'message_thread_id': topic_id, 'parse_mode': 'HTML',
        })
        try:
            return DeliveryResult(response.status)
        finally:
            response.close()

    async def parse_interaction(self, request: InteractionRequest) -> Interaction | ProviderResponse:
        try:
            payload = json.loads(request.body)
            if 'callback_query' not in payload:
                return ProviderResponse()
            callback = payload['callback_query']
            callback_id = callback['id']
            thread = callback['message']['message_thread_id']
            message = callback['message']['message_id']
            actor = callback['from']['id']
            action = callback['data']
            if not isinstance(callback_id, str) or not callback_id or not isinstance(thread, int) or not isinstance(message, int) or not isinstance(actor, int) or not isinstance(action, str):
                raise ValueError('invalid callback')
            if action in ('start_chain', 'stop_chain'):
                command = InteractionCommand(InteractionAction.TOGGLE_ASSIGNMENT)
            elif action == 'task':
                command = InteractionCommand(InteractionAction.CREATE_TASK)
            elif action == 'freeze_menu':
                command = InteractionCommand(InteractionAction.SHOW_FREEZE_OPTIONS)
            elif action == 'freeze_back':
                command = InteractionCommand(InteractionAction.NOOP)
            elif action in FREEZE_OPTIONS:
                command = InteractionCommand(InteractionAction.FREEZE, FREEZE_OPTIONS[action])
            elif action == 'noop':
                command = InteractionCommand(InteractionAction.NOOP)
            else:
                raise ValueError('unknown callback action')
            channel = callback['message'].get('chat', {}).get('id', '')
            return Interaction(MessageRef(channel, f'{thread}/{message}'), actor, (command,),
                               acknowledgement_id=callback_id)
        except (ValueError, TypeError, KeyError, AttributeError, json.JSONDecodeError):
            return ProviderResponse(status_code=400)

    async def acknowledge_interaction(self, interaction: Interaction) -> None:
        response = await self.http.post(f'{self.url}/answerCallbackQuery',
                                        json={'callback_query_id': interaction.acknowledgement_id}, headers=self.headers)
        response.close()

    async def after_interaction(self, message: IncidentPresentation, interaction: Interaction) -> None:
        show_menu = any(command.action == InteractionAction.SHOW_FREEZE_OPTIONS for command in interaction.commands)
        if show_menu and not message.can_unfreeze:
            await self._edit_message(message, freeze_menu=True)
        else:
            await self.update_incident(message)
        await self.acknowledge_interaction(interaction)

    @staticmethod
    def respond_to_interaction(message: IncidentPresentation) -> ProviderResponse:
        return ProviderResponse()

    @staticmethod
    def incident_url(message: MessageRef, identity: ProviderIdentity) -> str:
        return f'https://t.me/c/{str(message.channel_id)[4:]}/{message.thread_id}'

    @staticmethod
    def user_url(user: UserProfile, identity: ProviderIdentity) -> str | None:
        return f'https://t.me/{user.username}' if user.username else None

    @staticmethod
    def serialize_user(user: UserProfile, roles: list[str]) -> dict:
        return {
            'exists': user.exists, 'full_name': user.full_name,
            'id': int(user.id) if user.id is not None else None,
            'roles': list(roles), 'username': user.username,
        }

    @staticmethod
    def mention_id(user: UserProfile) -> int | None:
        return int(user.id) if user.id is not None else None

    @staticmethod
    def markdown_links(text: str) -> str:
        return text

    @staticmethod
    def template_source(name: str) -> str:
        if name not in TEMPLATE_NAMES:
            raise KeyError(name)
        return files(__package__).joinpath('resources').joinpath(name + '.j2').read_text(encoding='utf-8')
