"""Process-local discovery of trusted installed messenger providers."""

import re
from functools import lru_cache
from importlib.metadata import entry_points

from impulse_messenger_api import (
    PLUGIN_API_VERSION, REQUIRED_TEMPLATE_NAMES, BaseApplicationConfig,
    ProviderDescriptor, ProviderRegistration,
)


class ProviderRegistry:
    def __init__(self):
        self._providers: dict[str, ProviderRegistration] = {}

    def register(self, registration: ProviderRegistration) -> None:
        if not isinstance(registration, ProviderRegistration):
            raise ValueError('Messenger entry point must expose a ProviderRegistration')
        descriptor = registration.descriptor
        if not isinstance(descriptor, ProviderDescriptor):
            raise ValueError('Messenger registration must expose a ProviderDescriptor')
        provider_id = descriptor.provider_id
        if not isinstance(provider_id, str) or not re.fullmatch(r'[a-z][a-z0-9_-]*', provider_id):
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
            raise ValueError(
                f'Unknown application type: {provider_id} (messenger provider is not registered). '
                f'Install a compatible provider distribution exposing {provider_id!r} '
                'in the impulse.messengers entry point group, then restart IMPulse.'
            ) from None


def _validate_installed_provider(registration):
    provider_id = registration.descriptor.provider_id
    if not callable(registration.factory):
        raise ValueError(f'Messenger provider {provider_id} has no callable factory')
    if not isinstance(registration.config_model, type) or not issubclass(registration.config_model, BaseApplicationConfig):
        raise ValueError(f'Messenger provider {provider_id} has no compatible config model')
    if registration.authentication_factory is not None and not callable(registration.authentication_factory):
        raise ValueError(f'Messenger provider {provider_id} has no callable authentication factory')
    if registration.descriptor.messaging_enabled:
        if not callable(registration.template_source) or not callable(registration.incident_url):
            raise ValueError(f'Messenger provider {provider_id} requires templates and an incident URL factory')
        for name in REQUIRED_TEMPLATE_NAMES:
            try:
                source = registration.template_source(name)
            except Exception:
                raise ValueError(f'Messenger provider {provider_id} is missing required template: {name}') from None
            if not isinstance(source, str):
                raise ValueError(f'Messenger provider {provider_id} has an invalid template: {name}')


@lru_cache(maxsize=1)
def get_provider_registry() -> ProviderRegistry:
    """Discover once per process; package changes require a restart."""
    from app.im.providers.none import NoneProvider

    registry = ProviderRegistry()
    registry.register(ProviderRegistration(
        NoneProvider.descriptor, NoneProvider, config_model=NoneProvider.config_model,
    ))
    for entry_point in sorted(entry_points(group='impulse.messengers'), key=lambda item: item.name):
        if entry_point.name == 'none':
            raise ValueError('Messenger provider ID none is reserved for IMPulse')
        try:
            registration = entry_point.load()
        except Exception:
            distribution = getattr(getattr(entry_point, 'dist', None), 'name', 'unknown distribution')
            raise ValueError(f'Cannot load messenger provider {entry_point.name!r} from {distribution}') from None
        if not isinstance(registration, ProviderRegistration):
            raise ValueError(f'Messenger entry point {entry_point.name!r} must expose a ProviderRegistration')
        if not isinstance(registration.descriptor, ProviderDescriptor):
            raise ValueError(f'Messenger entry point {entry_point.name!r} must expose a ProviderDescriptor')
        if entry_point.name != registration.descriptor.provider_id:
            raise ValueError(f'Messenger entry point name {entry_point.name!r} does not match provider ID')
        registry.register(registration)
        _validate_installed_provider(registration)
    return registry
