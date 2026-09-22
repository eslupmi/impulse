"""Temporary bridge from the public DTO seam to the built-in payload helpers.

The old helpers still read configuration and template resources. Phases 2–3
remove those dependencies. This bridge never receives a mutable Incident and
does not own users, queues, task management or the HTTP client's lifetime.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from app.im.plugin_api import (
    DeliveryResult, GroupProfile, IncidentPresentation, MessageRef,
    NotificationContent, ProviderContext, ProviderIdentity, UserProfile,
)
from app.logging import logger


@dataclass(frozen=True)
class LegacyIncidentView:
    """Read-only shape accepted by the existing built-in payload builders."""

    presentation: IncidentPresentation

    def __getattr__(self, name):
        return getattr(self.presentation, name)

    @property
    def ts(self):
        return self.presentation.thread_id

    @property
    def is_frozen(self):
        return self.presentation.frozen

    @property
    def frozen_until(self):
        value = self.presentation.frozen_until
        return datetime.fromisoformat(value) if value else None

    def can_manual_unfreeze(self):
        return self.presentation.can_unfreeze


class LegacyProviderAdapter(ABC):
    """Shared API mechanics retained during the same-repository migration."""

    post_message_url: str | None
    headers: dict | None

    @abstractmethod
    async def _get_public_url(self, config):
        raise NotImplementedError

    @abstractmethod
    async def get_user_details(self, user_details):
        raise NotImplementedError

    @abstractmethod
    async def get_all_groups(self):
        raise NotImplementedError

    @abstractmethod
    def _post_thread_payload(self, channel_id, thread_id, text):
        raise NotImplementedError

    @abstractmethod
    def _build_user_profile_url(self, user_id, user):
        raise NotImplementedError

    def __init__(self, config):
        self._app_config = config
        self.type = config.type
        self.url = self._get_url(config).rstrip('/')
        self.team = self._get_team_name(config)
        self.public_url = None
        self.http = None
        self.rate_window = self.descriptor.rate_window_seconds
        self._initialize_specific_params()

    async def initialize(self, context: ProviderContext) -> ProviderIdentity:
        self.http = context.http
        self.context = context
        url = await self._get_public_url(self._app_config)
        self.public_url = url.rstrip('/') if url else url
        return ProviderIdentity(self.public_url, self.team)

    async def start(self) -> None:
        pass

    async def fetch_user(self, user_id: str | int) -> UserProfile:
        data = await self.get_user_details({'id': user_id})
        return UserProfile(**{key: data.get(key) for key in UserProfile.__dataclass_fields__})

    async def fetch_groups(self) -> tuple[GroupProfile, ...]:
        groups = await self.get_all_groups()
        return tuple(GroupProfile(id=id_, name=name) for id_, name in groups.items())

    async def create_incident(self, message: IncidentPresentation) -> MessageRef | None:
        thread_id = await self.create_incident_message(
            LegacyIncidentView(message), message.body, message.header, message.status_icon,
        )
        return MessageRef(message.channel_id, str(thread_id)) if thread_id is not None else None

    async def create_incident_message(self, incident, body, header, status_icons):
        payload = self._get_incident_message_payload(incident, body, header, status_icons)
        return await self._send_create_incident_message(payload)

    async def update_incident(self, message: IncidentPresentation) -> None:
        await self._update_presentation(LegacyIncidentView(message))

    async def _update_presentation(self, incident):
        payload = self.update_incident_payload(
            incident, incident.body, incident.header, incident.status_icon, incident.timezone,
        )
        await self._update_incident_message(incident.ts, payload)

    def notification_text(self, content: NotificationContent) -> str:
        return content.text if content.header is None else content.header + '\n' + content.text

    async def post_notification(self, message: MessageRef, content: NotificationContent) -> DeliveryResult:
        payload = self._post_thread_payload(message.channel_id, message.thread_id, self.notification_text(content))
        assert self.post_message_url is not None
        response = await self.http.post(self.post_message_url, headers=self.headers, json=payload)
        try:
            return DeliveryResult(response.status)
        finally:
            response.close()

    @abstractmethod
    def user_url(self, user: UserProfile, identity: ProviderIdentity) -> str | None:
        raise NotImplementedError

    @staticmethod
    async def _read_response_json(response):
        try:
            return await response.json()
        finally:
            response.close()

    async def _send_create_incident_message(self, payload):
        response = await self.http.post(self.post_message_url, headers=self.headers, json=payload)
        status = response.status
        try:
            response_json = await response.json()
        finally:
            response.close()
        if not 200 <= status < 300 or ('ok' in response_json and response_json.get('ok') is not True):
            logger.error(
                'Incident message creation failed',
                extra={
                    'messenger': self.type.value,
                    'channel_id': payload.get('channel_id') or payload.get('channel'),
                    'status': status,
                    'error': response_json.get('error') or response_json.get('message'),
                    'body': response_json,
                },
            )
            return None
        return response_json.get(self.thread_id_key)
