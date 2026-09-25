"""Slack platform adapter. Imports only the public API and owned resources."""
import hashlib
import hmac
import json
import logging
import re
import time
from importlib.resources import files
from urllib.parse import parse_qs

from app.im.plugin_api import (
    DeliveryResult, GroupProfile, IncidentPresentation, Interaction, InteractionAction,
    InteractionCommand, InteractionRequest, MessageRef, NotificationContent,
    ProviderContext, ProviderDescriptor, ProviderIdentity, ProviderResponse, SecretResolver, UserProfile,
)
from .config import SlackApplicationConfig
from .payloads import get_incident_message_payload, slack_get_update_payload

logger = logging.getLogger('main_logger')


class SlackProvider:
    descriptor = ProviderDescriptor('slack', rate_limit=10, rate_window_seconds=1.0)
    config_model = SlackApplicationConfig

    def __init__(self, config: SlackApplicationConfig, secrets: SecretResolver):
        address = secrets.get('DEV_MESSENGER_CUSTOM_ADDRESS')
        self.url = ((address.strip() if address else '') or 'https://slack.com').rstrip('/')
        self.team = None
        self.public_url = None
        self._token = secrets.get('SLACK_BOT_USER_OAUTH_TOKEN')
        self._verification_token = secrets.get('SLACK_VERIFICATION_TOKEN')
        self._signing_secret = secrets.get('SLACK_SIGNING_SECRET')
        if not self._token:
            raise ValueError('SLACK_BOT_USER_OAUTH_TOKEN is required')
        if not (self._verification_token or self._signing_secret):
            raise ValueError('SLACK_VERIFICATION_TOKEN or SLACK_SIGNING_SECRET is required')
        self.headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {self._token}'}

    async def initialize(self, context: ProviderContext) -> ProviderIdentity:
        self.http = context.http
        data, status = await self._read(await self.http.get(f'{self.url}/api/auth.test', headers=self.headers))
        self.public_url = data.get('url') if status == 200 and data.get('ok', True) else None
        if self.public_url:
            self.public_url = self.public_url.rstrip('/')
        return ProviderIdentity(self.public_url)

    async def start(self) -> None:
        pass

    @staticmethod
    async def _read(response, *, success_only=False):
        try:
            if success_only and response.status != 200:
                return {}, response.status
            return await response.json(), response.status
        finally:
            response.close()

    async def fetch_user(self, user_id: str | int) -> UserProfile:
        data, status = await self._read(await self.http.get(
            f'{self.url}/api/users.info', params={'user': user_id}, headers=self.headers), success_only=True)
        if status != 200 or not data.get('ok'):
            return UserProfile(id=user_id, exists=False)
        user = data.get('user', {})
        profile = user.get('profile', {})
        return UserProfile(id=user_id, exists=True, full_name=profile.get('real_name_normalized'),
                           username=user.get('name'), email=profile.get('email'), timezone=user.get('tz'))

    async def fetch_groups(self) -> tuple[GroupProfile, ...]:
        data, status = await self._read(await self.http.get(f'{self.url}/api/usergroups.list', headers=self.headers), success_only=True)
        if status != 200 or not data.get('ok'):
            return ()
        return tuple(GroupProfile(id=group['id'], name=group.get('name'))
                     for group in data.get('usergroups', []) if group.get('id'))

    @staticmethod
    def payload(message: IncidentPresentation, *, update=False):
        builder = slack_get_update_payload if update else get_incident_message_payload
        return builder(message, message.body, message.header, message.status_icon, message.timezone)

    async def create_incident(self, message: IncidentPresentation) -> MessageRef | None:
        data, status = await self._read(await self.http.post(
            f'{self.url}/api/chat.postMessage', headers=self.headers, json=self.payload(message)))
        if not 200 <= status < 300 or data.get('ok') is not True:
            # Never log a provider response body: it can echo credentials or user content.
            logger.error('Incident message creation failed', extra={'messenger': 'slack', 'status': status})
            return None
        ts = data.get('ts')
        return MessageRef(message.channel_id, str(ts)) if ts is not None else None

    async def update_incident(self, message: IncidentPresentation) -> None:
        response = await self.http.post(f'{self.url}/api/chat.update', headers=self.headers,
                                        json=self.payload(message, update=True))
        response.close()

    async def post_notification(self, message: MessageRef, content: NotificationContent) -> DeliveryResult:
        text = content.text if content.header is None else content.header + '\n' + content.text
        response = await self.http.post(f'{self.url}/api/chat.postMessage', headers=self.headers,
            json={'channel': message.channel_id, 'thread_ts': message.thread_id, 'text': text,
                  'unfurl_links': False, 'unfurl_media': False})
        try:
            return DeliveryResult(response.status)
        finally:
            response.close()

    @staticmethod
    def incident_url(message: MessageRef, identity: ProviderIdentity) -> str:
        return f'{identity.public_url}/archives/{message.channel_id}/p{message.thread_id.replace(".", "")}'

    @staticmethod
    def user_url(user: UserProfile, identity: ProviderIdentity) -> str:
        return f'{identity.public_url}/team/{user.id}'

    @staticmethod
    def mention_id(user: UserProfile):
        return user.id

    @staticmethod
    def markdown_links(text: str) -> str:
        return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<\2|\1>', text, flags=re.DOTALL)

    @staticmethod
    def template_source(name: str) -> str:
        if name not in TEMPLATE_NAMES:
            raise KeyError(name)
        return files(__package__).joinpath('resources').joinpath(name + '.j2').read_text(encoding='utf-8')

    async def parse_interaction(self, request: InteractionRequest) -> Interaction | ProviderResponse:
        # Signed installations cannot fall back to an unsigned verification token.
        if self._signing_secret:
            headers = {key.lower(): value for key, value in request.headers}
            timestamp = headers.get('x-slack-request-timestamp', '')
            try:
                if abs(int(time.time()) - int(timestamp)) > 300:
                    return ProviderResponse(status_code=401)
            except ValueError:
                return ProviderResponse(status_code=401)
            signature = 'v0=' + hmac.new(self._signing_secret.encode(),
                b'v0:' + timestamp.encode() + b':' + request.body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature.encode(), headers.get('x-slack-signature', '').encode()):
                return ProviderResponse(status_code=401)
        try:
            fields = parse_qs(request.body.decode(), keep_blank_values=True)
            payload = json.loads(fields['payload'][0])
            if not isinstance(payload, dict):
                raise ValueError('payload must be an object')
            if not self._signing_secret:
                token = payload.get('token')
                if not isinstance(token, str) or not self._verification_token or not hmac.compare_digest(token, self._verification_token):
                    return ProviderResponse(status_code=401)
            ts, actor = payload['message_ts'], payload['user']['id']
            if not isinstance(ts, str) or not ts or not isinstance(actor, str) or not actor:
                raise ValueError('invalid message or actor')
            channel = payload.get('channel', {}).get('id', '')
            if not isinstance(channel, str):
                raise ValueError('invalid channel')
            commands = []
            actions = payload['actions']
            if not isinstance(actions, list):
                raise ValueError('invalid actions')
            for action in actions:
                name = action['name']
                if name == 'chain':
                    commands.append(InteractionCommand(InteractionAction.TOGGLE_ASSIGNMENT))
                elif name == 'task':
                    commands.append(InteractionCommand(InteractionAction.CREATE_TASK))
                elif name == 'freeze':
                    options = action.get('selected_options', [])
                    option = options[0]['value'] if action.get('type') == 'select' and options else None
                    if option is not None and option not in {'tomorrow', 'next_monday', 'month', '6months'}:
                        raise ValueError('invalid freeze option')
                    commands.append(InteractionCommand(InteractionAction.FREEZE, option))
                else:
                    commands.append(InteractionCommand(InteractionAction.NOOP))
            original = ProviderResponse(json.dumps(payload.get('original_message')).encode())
            return Interaction(MessageRef(channel, ts), actor, tuple(commands), original)
        except (ValueError, KeyError, TypeError, IndexError, AttributeError):
            return ProviderResponse(status_code=400)

    def respond_to_interaction(self, message: IncidentPresentation) -> ProviderResponse:
        return ProviderResponse(json.dumps(self.payload(message, update=True)).encode())


TEMPLATE_NAMES = frozenset({
    'body', 'header', 'status_icons', 'chain_step_user', 'chain_step_user_group', 'chain_step_group',
    'chain_step_webhook', 'incident_notifications_assignment', 'incident_notifications_status_update',
    'incident_notifications_new_firing', 'incident_notifications_partial_resolved',
    'incident_notifications_freeze', 'incident_notifications_unfreeze',
})
