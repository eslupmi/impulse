"""Explicit, process-local registration. No imports from installed packages."""

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable

from app.im.plugin_api import PLUGIN_API_VERSION, MessengerProvider, ProviderDescriptor


@dataclass(frozen=True)
class ProviderRegistration:
    descriptor: ProviderDescriptor
    factory: Callable[..., MessengerProvider]
    config_model: type | None = None
    authentication_factory: Callable | None = None
    template_source: Callable | None = None
    incident_url: Callable | None = None


class ProviderRegistry:
    def __init__(self):
        self._providers: dict[str, ProviderRegistration] = {}

    def register(self, registration: ProviderRegistration) -> None:
        descriptor = registration.descriptor
        provider_id = descriptor.provider_id
        if not re.fullmatch(r'[a-z][a-z0-9_-]*', provider_id):
            raise ValueError(f'Invalid messenger provider ID: {provider_id!r}')
        if descriptor.api_version != PLUGIN_API_VERSION:
            raise ValueError(f'Incompatible messenger provider API: {provider_id} (expected {PLUGIN_API_VERSION})')
        if descriptor.rate_limit is not None and descriptor.rate_limit <= 0:
            raise ValueError(f'Invalid messenger rate limit: {provider_id}')
        if descriptor.rate_window_seconds <= 0:
            raise ValueError(f'Invalid messenger rate window: {provider_id}')
        if provider_id in self._providers:
            raise ValueError(f'Duplicate messenger provider: {provider_id}')
        self._providers[provider_id] = registration

    def resolve(self, provider_id: str) -> ProviderRegistration:
        if not isinstance(provider_id, str):
            raise ValueError('Invalid messenger provider ID: expected a string')
        try:
            return self._providers[provider_id]
        except KeyError:
            raise ValueError(f'Unknown application type: {provider_id} (messenger provider is not registered)') from None


@lru_cache(maxsize=1)
def get_provider_registry() -> ProviderRegistry:
    # The sole built-in composition root. These imports are deliberately lazy:
    # config parsing and provider contracts do not import runtime applications.
    from app.im.providers.slack import SlackProvider
    from app.im.providers.slack.authentication import SlackAuthentication
    from app.im.providers.mattermost import MattermostProvider
    from app.im.providers.mattermost.authentication import MattermostAuthentication
    from app.im.providers.none import NoneProvider
    from app.im.providers.telegram import TelegramProvider
    from app.im.providers.telegram.authentication import TelegramAuthentication

    registry = ProviderRegistry()
    def authentication(protocol):
        return lambda client_id, client_secret, messenger: protocol(client_id, client_secret)

    registry.register(ProviderRegistration(
        SlackProvider.descriptor, SlackProvider, config_model=SlackProvider.config_model,
        authentication_factory=authentication(SlackAuthentication), template_source=SlackProvider.template_source,
        incident_url=SlackProvider.incident_url,
    ))
    registry.register(ProviderRegistration(
        MattermostProvider.descriptor, MattermostProvider, config_model=MattermostProvider.config_model,
        authentication_factory=lambda client_id, client_secret, messenger: MattermostAuthentication(
            messenger.address, client_id, client_secret),
        template_source=MattermostProvider.template_source, incident_url=MattermostProvider.incident_url,
    ))
    registry.register(ProviderRegistration(
        NoneProvider.descriptor, NoneProvider, config_model=NoneProvider.config_model,
    ))
    registry.register(ProviderRegistration(
        TelegramProvider.descriptor, TelegramProvider, config_model=TelegramProvider.config_model,
        authentication_factory=authentication(TelegramAuthentication),
        template_source=TelegramProvider.template_source, incident_url=TelegramProvider.incident_url,
    ))
    return registry
