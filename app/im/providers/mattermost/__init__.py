"""Mattermost platform adapter. Imports only the public API and owned resources."""
import asyncio
import json
import logging
from importlib.resources import files

import aiohttp

from app.im.plugin_api import (
    DeliveryResult, GroupProfile, IncidentPresentation, Interaction, InteractionAction,
    InteractionCommand, InteractionRequest, MessageRef, NotificationContent,
    ProviderContext, ProviderDescriptor, ProviderIdentity, ProviderResponse, SecretResolver, UserProfile,
)
from .config import MattermostApplicationConfig
from .payloads import (
    mattermost_get_button_update_payload, mattermost_get_create_thread_payload, mattermost_get_update_payload,
)

logger = logging.getLogger('main_logger')

FREEZE_OPTIONS = frozenset({'tomorrow', 'next_monday', 'month', '6months'})


class MattermostProvider:
    descriptor = ProviderDescriptor('mattermost', rate_limit=10, rate_window_seconds=1.0, user_update_gap_seconds=2.0)
    config_model = MattermostApplicationConfig

    def __init__(self, config: MattermostApplicationConfig, secrets: SecretResolver):
        self.url = config.address.rstrip('/')
        self.team = config.team
        self.callback_url = None
        self._groups = tuple(group.id for group in config.groups.values())
        token = secrets.get('MATTERMOST_ACCESS_TOKEN')
        if not token:
            raise ValueError('MATTERMOST_ACCESS_TOKEN is required')
        self.headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}

    async def initialize(self, context: ProviderContext) -> ProviderIdentity:
        self.http = context.http
        self.callback_url = context.callback_url
        return ProviderIdentity(self.url, self.team)

    async def activate(self) -> None:
        pass

    @staticmethod
    async def _read_json(response):
        try:
            return await response.json()
        finally:
            response.close()

    async def fetch_user(self, user_id: str | int) -> UserProfile:
        response = await self.http.get(
            f'{self.url}/api/v4/users/{user_id}?user_id={user_id}', headers=self.headers)
        status = response.status
        if status != 200:
            response.close()
            logger.debug('User details fetch failed', extra={'user_id': user_id, 'status': status})
            return UserProfile(id=user_id, exists=False)
        data = await self._read_json(response)
        return UserProfile(
            id=user_id, exists=True, full_name=self._full_name(data), username=data.get('username'),
            email=data.get('email'), timezone=self._extract_timezone(data.get('timezone')),
        )

    async def fetch_groups(self) -> tuple[GroupProfile, ...]:
        profiles = []
        for group_id in self._groups:
            try:
                response = await self.http.get(f'{self.url}/api/v4/groups/{group_id}', headers=self.headers)
            except (asyncio.TimeoutError, aiohttp.ClientConnectionError) as error:
                logger.error('Group details fetch error', extra={'group_id': group_id, 'error': str(error)})
                profiles.append(GroupProfile(id=group_id, name=None, exists=False))
                continue
            status = response.status
            if status != 200:
                response.close()
                logger.debug('Group details fetch failed', extra={'group_id': group_id, 'status': status})
                profiles.append(GroupProfile(id=group_id, name=None, exists=False))
            else:
                data = await self._read_json(response)
                profiles.append(GroupProfile(id=group_id, name=data.get('name')))
        return tuple(profiles)

    def payload(self, message: IncidentPresentation, *, update=False):
        builder = mattermost_get_update_payload if update else mattermost_get_create_thread_payload
        return builder(message, message.body, message.header, message.status_icon, self.callback_url)

    async def create_incident(self, message: IncidentPresentation) -> MessageRef | None:
        response = await self.http.post(
            f'{self.url}/api/v4/posts', headers=self.headers, json=self.payload(message))
        status = response.status
        data = await self._read_json(response)
        if not 200 <= status < 300:
            logger.error('Incident message creation failed', extra={'messenger': 'mattermost', 'status': status})
            return None
        post_id = data.get('id')
        return MessageRef(message.channel_id, str(post_id)) if post_id else None

    async def update_incident(self, message: IncidentPresentation) -> None:
        response = await self.http.put(
            f'{self.url}/api/v4/posts/{message.thread_id}', headers=self.headers, json=self.payload(message, update=True))
        response.close()

    async def post_notification(self, message: MessageRef, content: NotificationContent) -> DeliveryResult:
        text = content.text if content.header is None else content.header + '\n' + content.text
        response = await self.http.post(f'{self.url}/api/v4/posts', headers=self.headers, json={
            'channel_id': message.channel_id, 'root_id': message.thread_id, 'message': text,
        })
        try:
            return DeliveryResult(response.status)
        finally:
            response.close()

    @staticmethod
    def incident_url(message: MessageRef, identity: ProviderIdentity) -> str:
        return f'{identity.public_url}/{identity.team.lower()}/pl/{message.thread_id}'

    @staticmethod
    def user_url(user: UserProfile, identity: ProviderIdentity) -> str:
        return f'{identity.public_url}/{identity.team}/users/{user.id}'

    @staticmethod
    def mention_id(user: UserProfile):
        return user.username

    @staticmethod
    def template_source(name: str) -> str:
        if name not in TEMPLATE_NAMES:
            raise KeyError(name)
        return files(__package__).joinpath('resources').joinpath(name + '.j2').read_text(encoding='utf-8')

    async def parse_interaction(self, request: InteractionRequest) -> Interaction | ProviderResponse:
        try:
            payload = json.loads(request.body)
            if not isinstance(payload, dict):
                raise ValueError('payload must be an object')
            post_id, actor = payload['post_id'], payload.get('user_id')
            if not isinstance(post_id, str) or not post_id or not isinstance(actor, str) or not actor:
                raise ValueError('invalid message or actor')
            channel = payload.get('channel_id') or ''
            if not isinstance(channel, str):
                raise ValueError('invalid channel')
            context = payload.get('context') or {}
            if not isinstance(context, dict):
                raise ValueError('invalid context')
            action = context.get('action')
            if action == 'chain':
                command = InteractionCommand(InteractionAction.TOGGLE_ASSIGNMENT)
            elif action == 'task':
                command = InteractionCommand(InteractionAction.CREATE_TASK)
            elif action == 'unfreeze':
                command = InteractionCommand(InteractionAction.UNFREEZE)
            else:
                selected = context.get('selected_option')
                option = selected.removeprefix('freeze_') if isinstance(selected, str) and selected.startswith('freeze_') else None
                if option is not None and option not in FREEZE_OPTIONS:
                    raise ValueError('invalid freeze option')
                command = InteractionCommand(InteractionAction.FREEZE, option) if option else InteractionCommand(InteractionAction.NOOP)
            return Interaction(MessageRef(channel, post_id), actor, (command,), ProviderResponse(request.body))
        except (json.JSONDecodeError, ValueError, KeyError, TypeError, AttributeError):
            return ProviderResponse(status_code=400)

    def respond_to_interaction(self, message: IncidentPresentation) -> ProviderResponse:
        body = mattermost_get_button_update_payload(
            message, message.body, message.header, message.status_icon, self.callback_url)
        return ProviderResponse(json.dumps(body).encode())

    @staticmethod
    def _full_name(data):
        return f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()

    @staticmethod
    def _extract_timezone(timezone_data):
        if not timezone_data or not isinstance(timezone_data, dict):
            return None
        if timezone_data.get('useAutomaticTimezone') == 'true':
            return timezone_data.get('automaticTimezone') or None
        return timezone_data.get('manualTimezone') or None


TEMPLATE_NAMES = frozenset({
    'body', 'header', 'status_icons', 'chain_step_user', 'chain_step_user_group', 'chain_step_group',
    'chain_step_webhook', 'incident_notifications_assignment', 'incident_notifications_status_update',
    'incident_notifications_new_firing', 'incident_notifications_partial_resolved',
    'incident_notifications_freeze', 'incident_notifications_unfreeze',
})
