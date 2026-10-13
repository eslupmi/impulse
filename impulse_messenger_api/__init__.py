"""Version 1 public API for trusted, installed messenger providers.

Providers receive rendered values and injected HTTP transport, never mutable
incidents, queues, application configuration singletons or HTTP sessions.
"""

from dataclasses import dataclass
from typing import Any, Callable, Protocol, runtime_checkable


# Shared schema is public; providers never import app.config.
from .schema import BaseApplicationConfig, BaseUser, HttpBase

from collections.abc import Mapping
from enum import Enum


PLUGIN_API_VERSION = 1


@dataclass(frozen=True)
class ProviderDescriptor:
    provider_id: str
    api_version: int = PLUGIN_API_VERSION
    rate_limit: int | None = None
    rate_window_seconds: float = 1.0
    messaging_enabled: bool = True
    user_update_gap_seconds: float = 1.0
    notification_headers: bool = True
    refresh_inhibition_source: bool = True
    html_autoescape: bool = False
    allow_inhibited_freeze_actions: bool = False


@dataclass(frozen=True)
class MessageRef:
    """Configured platform channel ID plus a thread ID unique within that channel.

    Providers keep the configured channel ID unchanged in returned references.
    """
    channel_id: str | int
    thread_id: str


@dataclass(frozen=True)
class ProviderIdentity:
    public_url: str | None = None
    team: str | None = None


@dataclass(frozen=True)
class UserProfile:
    id: str | int | None
    exists: bool
    full_name: str | None = None
    username: str | None = None
    email: str | None = None
    timezone: str | None = None


@dataclass(frozen=True)
class GroupProfile:
    id: str
    name: str | None
    exists: bool = True


@dataclass(frozen=True)
class IncidentPresentation:
    channel_id: str | int
    thread_id: str | None
    status: str
    header: str
    body: str
    status_icon: str
    chain_enabled: bool
    frozen: bool
    frozen_by_inhibition: bool
    frozen_by_maintenance: bool
    frozen_until: str | None
    can_unfreeze: bool
    task_link: str
    timezone: str | None = None
    frozen_until_text: str | None = None
    can_create_task: bool = False


@dataclass(frozen=True)
class NotificationContent:
    text: str
    header: str | None = None


@dataclass(frozen=True)
class DeliveryResult:
    status_code: int


class MessengerHttpResponse(Protocol):
    @property
    def status(self) -> int: ...

    async def json(self) -> Any: ...

    def close(self) -> None: ...


class MessengerHttpTransport(Protocol):
    """Core owns the transport lifetime; providers close individual responses."""

    async def get(self, url: str, **kwargs: Any) -> MessengerHttpResponse: ...

    async def post(self, url: str, **kwargs: Any) -> MessengerHttpResponse: ...

    async def put(self, url: str, **kwargs: Any) -> MessengerHttpResponse: ...


@dataclass(frozen=True)
class ProviderContext:
    http: MessengerHttpTransport
    callback_url: str | None
    api_version: int = PLUGIN_API_VERSION


@runtime_checkable
class MessengerProvider(Protocol):
    descriptor: ProviderDescriptor

    @property
    def url(self) -> str: ...

    @property
    def team(self) -> str | None: ...

    async def initialize(self, context: ProviderContext) -> ProviderIdentity:
        """Attach transport/context and resolve identity before loading users/groups."""
        ...

    async def activate(self) -> None:
        """Activate external callbacks after core users/groups/admins are ready."""
        ...

    async def fetch_user(self, user_id: str | int) -> UserProfile: ...

    async def fetch_groups(self) -> tuple[GroupProfile, ...]: ...

    async def create_incident(self, message: IncidentPresentation) -> MessageRef | None: ...

    async def update_incident(self, message: IncidentPresentation) -> None: ...

    async def post_notification(self, message: MessageRef, content: NotificationContent) -> DeliveryResult: ...

    def user_url(self, user: UserProfile, identity: ProviderIdentity) -> str | None: ...



class SecretResolver(Protocol):
    def get(self, name: str, default: str = '') -> str: ...


class InteractionAction(str, Enum):
    TOGGLE_ASSIGNMENT = 'toggle_assignment'
    ASSIGN = 'assign'
    RELEASE = 'release'
    FREEZE = 'freeze'
    UNFREEZE = 'unfreeze'
    CREATE_TASK = 'create_task'
    NOOP = 'noop'
    SHOW_FREEZE_OPTIONS = 'show_freeze_options'


@dataclass(frozen=True)
class InteractionRequest:
    method: str
    headers: tuple[tuple[str, str], ...]
    query: tuple[tuple[str, str], ...]
    body: bytes


@dataclass(frozen=True)
class InteractionCommand:
    action: InteractionAction
    freeze_option: str | None = None


@dataclass(frozen=True)
class ProviderResponse:
    # Serialized bytes keep arbitrary provider response data deeply immutable.
    body: bytes = b'{}'
    status_code: int = 200
    media_type: str = 'application/json'


@dataclass(frozen=True)
class Interaction:
    message: MessageRef
    actor_id: str | int
    commands: tuple[InteractionCommand, ...]
    original_response: ProviderResponse = ProviderResponse()
    acknowledgement_id: str | None = None


@dataclass(frozen=True)
class AuthenticationUser:
    id: str
    username: str | None = None
    full_name: str | None = None
    email: str | None = None
    timezone: str | None = None


class AuthenticationError(Exception):
    def __init__(self, code: str, message: str = ''):
        self.code = code
        super().__init__(message or code)


class ProviderAuthentication(Protocol):
    name: str
    def build_authorization_url(self, state: str, redirect_uri: str) -> str: ...
    async def authenticate_callback(self, params: Mapping[str, str], redirect_uri: str,
                                    http: MessengerHttpTransport) -> AuthenticationUser: ...


@runtime_checkable
class InteractiveProvider(MessengerProvider, Protocol):
    async def parse_interaction(self, request: InteractionRequest) -> Interaction | ProviderResponse: ...
    def respond_to_interaction(self, message: IncidentPresentation) -> ProviderResponse: ...
    def incident_url(self, message: MessageRef, identity: ProviderIdentity) -> str: ...
    def template_source(self, name: str) -> str: ...
    def mention_id(self, user: UserProfile) -> str | int | None: ...


REQUIRED_TEMPLATE_NAMES = (
    'body', 'header', 'status_icons', 'chain_step_user', 'chain_step_user_group',
    'chain_step_group', 'chain_step_webhook', 'incident_notifications_assignment',
    'incident_notifications_status_update', 'incident_notifications_new_firing',
    'incident_notifications_partial_resolved', 'incident_notifications_freeze',
    'incident_notifications_unfreeze',
)


@dataclass(frozen=True)
class ProviderRegistration:
    """Value exposed by an ``impulse.messengers`` distribution entry point."""

    descriptor: ProviderDescriptor
    factory: Callable[..., MessengerProvider]
    config_model: type[BaseApplicationConfig] | None = None
    authentication_factory: Callable | None = None
    template_source: Callable[[str], str] | None = None
    incident_url: Callable | None = None


__all__ = [
    'PLUGIN_API_VERSION', 'REQUIRED_TEMPLATE_NAMES', 'BaseApplicationConfig',
    'BaseUser', 'HttpBase', 'ProviderDescriptor', 'MessageRef',
    'ProviderIdentity', 'UserProfile', 'GroupProfile', 'IncidentPresentation',
    'NotificationContent', 'DeliveryResult', 'MessengerHttpResponse',
    'MessengerHttpTransport', 'ProviderContext', 'MessengerProvider', 'SecretResolver',
    'InteractionAction', 'InteractionRequest', 'InteractionCommand', 'ProviderResponse',
    'Interaction', 'AuthenticationUser', 'AuthenticationError', 'ProviderAuthentication',
    'InteractiveProvider', 'ProviderRegistration',
]
