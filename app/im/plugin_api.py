"""Version 1 of the in-process messenger seam (no package discovery).

This module deliberately imports no Impulse implementation modules. Providers
receive rendered values, never incidents, queues, user stores or HTTP sessions.
Configuration and callback adapters are still internal during Phase 1.
"""

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


PLUGIN_API_VERSION = 1


@dataclass(frozen=True)
class ProviderDescriptor:
    provider_id: str
    api_version: int = PLUGIN_API_VERSION
    rate_limit: int | None = None
    rate_window_seconds: float = 1.0
    messaging_enabled: bool = True


@dataclass(frozen=True)
class MessageRef:
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

    async def initialize(self, context: ProviderContext) -> ProviderIdentity: ...

    async def start(self) -> None: ...

    async def fetch_user(self, user_id: str | int) -> UserProfile: ...

    async def fetch_groups(self) -> tuple[GroupProfile, ...]: ...

    async def create_incident(self, message: IncidentPresentation) -> MessageRef | None: ...

    async def update_incident(self, message: IncidentPresentation) -> None: ...

    async def post_notification(self, message: MessageRef, content: NotificationContent) -> DeliveryResult: ...

    def user_url(self, user: UserProfile, identity: ProviderIdentity) -> str | None: ...
