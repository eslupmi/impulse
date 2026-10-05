"""Installed messenger discovery, compatibility, and startup failure contracts."""

import traceback
from dataclasses import replace
from importlib import import_module
from importlib.metadata import entry_points
from types import SimpleNamespace
from typing import Literal
from unittest.mock import AsyncMock, Mock

import pytest

import impulse_messenger_api as api
from app.config.validation import ImpulseConfig
from app.im import registry as registry_module
from app.im.helpers import get_application
from app.im.providers.none import NoneProvider
from app.im.registry import get_provider_registry
from impulse_messenger_api import (
    BaseApplicationConfig,
    ProviderDescriptor,
    ProviderRegistration,
)


class ThirdPartyConfig(BaseApplicationConfig):
    type: Literal['acme_chat'] = 'acme_chat'
    endpoint: str = 'https://chat.example.test'


class ThirdPartyProvider(NoneProvider):
    descriptor = ProviderDescriptor('acme_chat', messaging_enabled=False)
    config_model = ThirdPartyConfig


REGISTRATION = ProviderRegistration(
    ThirdPartyProvider.descriptor, ThirdPartyProvider, config_model=ThirdPartyConfig,
)
MESSAGING_REGISTRATION = replace(
    REGISTRATION, descriptor=replace(REGISTRATION.descriptor, messaging_enabled=True),
    template_source=lambda name: '{{ body }}', incident_url=lambda message, identity: 'https://chat.example.test',
)


def installed_entry_point(name='acme_chat', registration=REGISTRATION):
    return SimpleNamespace(name=name, dist=SimpleNamespace(name='example-provider'), load=Mock(return_value=registration))


@pytest.fixture(autouse=True)
def clear_registry_cache():
    get_provider_registry.cache_clear()
    yield
    get_provider_registry.cache_clear()


def discover(monkeypatch, *entries):
    loader = Mock(return_value=list(entries))
    monkeypatch.setattr(registry_module, 'entry_points', loader)
    return loader


def test_public_api_owns_shared_schema_and_retired_modules_are_absent():
    from impulse_messenger_api import schema

    for name in ('BaseApplicationConfig', 'BaseUser', 'HttpBase'):
        assert getattr(api, name) is getattr(schema, name), name
    assert registry_module.ProviderRegistration is ProviderRegistration
    for module in ('app.im.plugin_api', 'app.im.plugin_config', 'app.im.providers.legacy', 'app.im.colors'):
        with pytest.raises(ModuleNotFoundError):
            import_module(module)


@pytest.mark.parametrize('provider_id, class_name', [
    ('slack', 'SlackProvider'), ('mattermost', 'MattermostProvider'), ('telegram', 'TelegramProvider'),
])
def test_installed_distribution_entry_points_drive_the_production_registry(provider_id, class_name):
    entries = [entry for entry in entry_points(group='impulse.messengers') if entry.name == provider_id]
    assert len(entries) == 1
    entry = entries[0]
    assert entry.dist.name.replace('_', '-') == f'impulse-{provider_id}'
    registration = entry.load()
    assert isinstance(registration, ProviderRegistration)
    assert registration is get_provider_registry().resolve(provider_id)
    assert registration.factory is getattr(import_module(f'impulse_{provider_id}'), class_name)
    assert registration.config_model is registration.factory.config_model


def test_discovery_runs_once_for_the_process_lifetime(monkeypatch):
    entry = installed_entry_point()
    loader = discover(monkeypatch, entry)
    first = get_provider_registry()
    entry.load.assert_not_called()
    loader.return_value = []
    assert get_provider_registry() is first
    entry.load.assert_not_called()
    assert first.resolve('acme_chat') is REGISTRATION
    assert first.resolve('acme_chat') is REGISTRATION
    loader.assert_called_once_with(group='impulse.messengers')
    entry.load.assert_called_once_with()


def test_no_installed_providers_keeps_none_and_explains_missing_package(monkeypatch):
    discover(monkeypatch)
    registry = get_provider_registry()
    assert registry.resolve('none').factory is NoneProvider
    with pytest.raises(ValueError) as error:
        registry.resolve('slack')
    assert 'not registered' in str(error.value)
    assert 'Install' in str(error.value) and 'impulse.messengers' in str(error.value)
    assert 'restart' in str(error.value)


def test_third_party_string_id_survives_config_round_trip_and_facade_creation(monkeypatch):
    selected = installed_entry_point()
    broken = installed_entry_point('broken_chat')
    broken.load.side_effect = ImportError('unused dependency is missing')
    invalid = installed_entry_point('Bad ID', registration=object())
    duplicates = [installed_entry_point('unused_chat'), installed_entry_point('unused_chat')]
    discover(monkeypatch, selected, broken, invalid, *duplicates)
    data = {
        'messenger': {'type': 'acme_chat', 'admin_users': [], 'channels': {'default': {'id': 'C1'}},
                      'endpoint': 'https://custom.example.test'},
        'route': {'channel': 'default'},
    }
    config = ImpulseConfig.model_validate(data)
    assert type(config.messenger) is ThirdPartyConfig
    restored = ImpulseConfig.model_validate(config.model_dump())
    assert restored.messenger.type == 'acme_chat'
    assert restored.messenger.endpoint == 'https://custom.example.test'
    app = get_application(restored.messenger, restored.messenger.channels, 'default')
    assert app.type == 'acme_chat'
    assert type(app.provider) is ThirdPartyProvider
    assert app.provider.descriptor.provider_id == 'acme_chat'
    selected.load.assert_called_once_with()
    for entry in (broken, invalid, *duplicates):
        entry.load.assert_not_called()


@pytest.mark.asyncio
async def test_third_party_dictionary_groups_initialize_through_public_config(monkeypatch):
    provider = Mock(
        spec=api.InteractiveProvider, descriptor=MESSAGING_REGISTRATION.descriptor, url='', team=None,
        template_source=MESSAGING_REGISTRATION.template_source,
        initialize=AsyncMock(return_value=api.ProviderIdentity()), activate=AsyncMock(),
        fetch_groups=AsyncMock(return_value=(api.GroupProfile('G1', 'Responders'),)),
    )
    registration = replace(MESSAGING_REGISTRATION, factory=Mock(return_value=provider))
    discover(monkeypatch, installed_entry_point(registration=registration))
    config = ImpulseConfig.model_validate({
        'messenger': {'type': 'acme_chat', 'admin_users': [], 'channels': {'default': {'id': 'C1'}},
                      'groups': {'responders': {'id': 'G1'}, 'missing': {'id': 'G2'}}},
        'route': {'channel': 'default'},
    })
    assert config.messenger.groups['responders'] == {'id': 'G1'}
    app = get_application(config.messenger, config.messenger.channels, 'default')
    transport = Mock(close=AsyncMock())
    monkeypatch.setattr(app, '_setup_http', lambda: transport)
    try:
        await app.initialize_async()
        assert (app.groups['responders'].id, app.groups['responders'].name, app.groups['responders'].exists) == ('G1', 'Responders', True)
        assert (app.groups['missing'].id, app.groups['missing'].exists) == ('G2', False)
        provider.activate.assert_awaited_once()
    finally:
        await app.close()


def test_installed_none_entry_points_never_replace_builtin_provider(monkeypatch):
    entries = [installed_entry_point('none'), installed_entry_point('none')]
    for entry in entries:
        entry.load.side_effect = ImportError('unused dependency is missing')
    discover(monkeypatch, *entries)
    assert get_provider_registry().resolve('none').factory is NoneProvider
    assert ImpulseConfig.model_validate({'messenger': {'type': 'none'}}).messenger.type == 'none'
    for entry in entries:
        entry.load.assert_not_called()


@pytest.mark.parametrize('entry, message', [
    (installed_entry_point('other'), 'does not match'),
    (installed_entry_point(registration=object()), 'ProviderRegistration'),
    (installed_entry_point(registration=replace(REGISTRATION, descriptor=object())), 'ProviderDescriptor'),
    (installed_entry_point('Bad ID', replace(REGISTRATION, descriptor=ProviderDescriptor('Bad ID'))), 'Invalid'),
    (installed_entry_point(registration=replace(REGISTRATION, descriptor=replace(REGISTRATION.descriptor, api_version=2))), 'Incompatible'),
    (installed_entry_point(registration=replace(REGISTRATION, factory=None)), 'factory'),
    (installed_entry_point(registration=replace(REGISTRATION, config_model=None)), 'config model'),
    (installed_entry_point(registration=replace(REGISTRATION, config_model=object)), 'config model'),
    (installed_entry_point(registration=replace(REGISTRATION, authentication_factory=1)), 'authentication factory'),
    (installed_entry_point(registration=replace(MESSAGING_REGISTRATION, template_source=None)), 'requires templates'),
    (installed_entry_point(registration=replace(MESSAGING_REGISTRATION, incident_url=None)), 'incident URL'),
    (installed_entry_point(registration=replace(MESSAGING_REGISTRATION, template_source=lambda name: None)), 'invalid template'),
])
def test_invalid_selected_provider_prevents_startup(monkeypatch, entry, message):
    discover(monkeypatch, entry)
    with pytest.raises(ValueError, match=message):
        get_provider_registry().resolve(entry.name)


def test_duplicate_selected_provider_id_fails_before_imports(monkeypatch):
    entries = [installed_entry_point(), installed_entry_point()]
    discover(monkeypatch, *entries)
    with pytest.raises(ValueError, match='Duplicate messenger provider: acme_chat'):
        get_provider_registry().resolve('acme_chat')
    for entry in entries:
        entry.load.assert_not_called()


@pytest.mark.parametrize('failed_registration, message', [
    (ImportError('missing dependency'), 'Cannot load'),
    (replace(REGISTRATION, config_model=None), 'config model'),
    (replace(MESSAGING_REGISTRATION, template_source=None), 'requires templates'),
])
def test_failed_selected_load_or_validation_is_not_cached(monkeypatch, failed_registration, message):
    entry = installed_entry_point()
    entry.load.side_effect = [failed_registration, REGISTRATION]
    discover(monkeypatch, entry)
    registry = get_provider_registry()
    with pytest.raises(ValueError, match=message):
        registry.resolve('acme_chat')
    assert registry.resolve('acme_chat') is REGISTRATION
    assert registry.resolve('acme_chat') is REGISTRATION
    assert entry.load.call_count == 2


def test_load_failure_names_provider_and_distribution_without_secret_exception(monkeypatch):
    entry = installed_entry_point()
    entry.load.side_effect = RuntimeError('request failed: https://host.test/token-secret-value')
    discover(monkeypatch, entry)
    with pytest.raises(ValueError) as error:
        get_provider_registry().resolve('acme_chat')
    assert 'acme_chat' in str(error.value) and 'example-provider' in str(error.value)
    assert 'token-secret-value' not in ''.join(traceback.format_exception(error.value))


def test_missing_required_resource_prevents_startup_without_exposing_loader_error(monkeypatch):
    def templates(name):
        if name == 'header':
            raise FileNotFoundError('token-secret-value')
        return '{{ body }}'

    entry = installed_entry_point(registration=replace(MESSAGING_REGISTRATION, template_source=templates))
    discover(monkeypatch, entry)
    with pytest.raises(ValueError) as error:
        get_provider_registry().resolve('acme_chat')
    assert 'acme_chat' in str(error.value) and 'header' in str(error.value)
    assert 'token-secret-value' not in ''.join(traceback.format_exception(error.value))


@pytest.mark.parametrize('provider_id', ['none', 'slack', 'mattermost', 'telegram'])
@pytest.mark.parametrize('explicit_type', [False, True])
def test_builtin_config_ids_remain_plain_yaml_strings(monkeypatch, provider_id, explicit_type):
    import yaml

    from app.im.user_store import UserStore
    from app.incident import migrator

    data = {
        'admin_users': [], 'users': {}, 'channels': {},
        'impulse_address': 'https://impulse.example.test',
        'address': 'https://mattermost.example.test', 'team': 'example',
    }
    if explicit_type:
        data['type'] = provider_id
    configuration = get_provider_registry().resolve(provider_id).config_model.model_validate(data)
    assert type(configuration.type) is str
    assert configuration.type == provider_id

    user_cache = UserStore.serialize(configuration.type, {'username': 'example'})
    assert yaml.safe_load(yaml.safe_dump(user_cache))['messenger_type'] == provider_id
    assert f'messenger_type: {provider_id}\n' in yaml.dump(user_cache)

    monkeypatch.setattr(migrator, 'get_config', lambda: SimpleNamespace(messenger=configuration))
    migrated = migrator.IncidentMigrator._migrate_v0_4_to_v3_0_0({'last_state': {}})
    assert type(migrated['messenger_type']) is str
    assert yaml.safe_load(yaml.safe_dump(migrated))['messenger_type'] == provider_id
