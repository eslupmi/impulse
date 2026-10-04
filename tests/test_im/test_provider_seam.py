"""Exercise the public provider protocol through the production composition root."""

import ast
import asyncio
import json
from importlib import import_module
import sys
from urllib.parse import urlencode
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from impulse_telegram.config import TelegramApplicationConfig
from impulse_mattermost.config import MattermostApplicationConfig
from app.im.providers.none import NullApplicationConfig
from impulse_slack.config import SlackApplicationConfig
from app.im.application import Application
from app.im.helpers import get_application
from impulse_messenger_api import GroupProfile, InteractiveProvider, InteractionRequest, MessageRef, MessengerProvider, PLUGIN_API_VERSION, ProviderContext, ProviderDescriptor, ProviderIdentity, ProviderResponse, UserProfile
from app.im.registry import ProviderRegistry, get_provider_registry
from app.im.users import UserManager


def interaction_request(payload):
    return InteractionRequest('POST', (), (), urlencode({'payload': json.dumps(payload)}).encode())


def json_request(payload):
    return InteractionRequest('POST', (), (), json.dumps(payload).encode())


class Response:
    def __init__(self, body, status=200):
        self.body, self.status = body, status
        self.closed = False

    async def json(self):
        return self.body

    def close(self):
        self.closed = True


class Transport:
    """Small protocol implementation: intentionally no aiohttp session API."""

    def __init__(self):
        self.calls = []
        self.responses = []
        self.closed = False

    async def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if url.endswith('/auth.test'):
            body = {'ok': True, 'url': 'https://workspace.slack.test/'}
        elif 'users.info' in url:
            body = {'ok': True, 'user': {'name': 'alice', 'tz': 'UTC', 'profile': {'real_name_normalized': 'Alice'}}}
        elif '/users/' in url:
            body = {'username': 'alice', 'first_name': 'Alice', 'timezone': {'useAutomaticTimezone': 'true', 'automaticTimezone': 'UTC'}}
        elif '/getChat?' in url:
            body = {'ok': True, 'result': {'username': 'alice', 'first_name': 'Alice'}}
        elif url.endswith('/usergroups.list'):
            body = {'ok': True, 'usergroups': [{'id': 'G1', 'name': 'group'}]}
        elif '/groups/' in url:
            body = {'name': 'group'}
        elif url.endswith('/createForumTopic'):
            body = {'ok': True, 'result': {'message_thread_id': 10}}
        elif url.endswith('/sendMessage'):
            body = {'ok': True, 'result': {'message_id': 20}}
        else:
            body = {'ok': True, 'ts': '123.456', 'id': 'post-1'}
        response = Response(body)
        self.responses.append(response)
        return response

    async def get(self, url, **kwargs):
        return await self.request('GET', url, **kwargs)

    async def post(self, url, **kwargs):
        return await self.request('POST', url, **kwargs)

    async def put(self, url, **kwargs):
        return await self.request('PUT', url, **kwargs)

    async def close(self):
        self.closed = True


def config_for(provider_id, **overrides):
    cls = {'slack': SlackApplicationConfig, 'mattermost': MattermostApplicationConfig,
           'telegram': TelegramApplicationConfig, 'none': NullApplicationConfig}[provider_id]
    values = dict(channels={'default': {'id': -100123 if provider_id == 'telegram' else 'C1'}},
                  users={}, admin_users=[], impulse_address='http://impulse.test')
    if provider_id == 'mattermost':
        values.update(address='https://mm.test', team='test-team')
    values.update(overrides)
    return cls(**values)


def incident_for(provider_id):
    return SimpleNamespace(
        channel_id=-100123 if provider_id == 'telegram' else 'C1', ts='', status='firing',
        chain_enabled=True, is_frozen=False, frozen_by_inhibition=False, frozen_by_maintenance=False,
        frozen_until=None, can_manual_unfreeze=lambda: False, task_link='', assigned_user_id='',
        payload={}, uniq_id='incident-1', dump=Mock(), release=Mock(),
    )


@pytest.fixture
def runtime(monkeypatch):
    monkeypatch.setenv('SLACK_BOT_USER_OAUTH_TOKEN', 'test-token')
    monkeypatch.setenv('SLACK_VERIFICATION_TOKEN', 'verify')
    monkeypatch.setenv('MATTERMOST_ACCESS_TOKEN', 'test-token')
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'test-token')
    config = SimpleNamespace(app=SimpleNamespace(task_management=None, general=SimpleNamespace(timezone='UTC')),
                             messenger=SimpleNamespace(impulse_address='http://impulse.test'))
    for module in ('app.im.application',):
        monkeypatch.setattr(module + '.get_config', lambda: config)
    store = Mock()
    store.get_all_users_by_type.return_value = {}
    monkeypatch.setattr('app.im.application.get_user_store', lambda: store)
    return config


def test_messaging_provider_must_be_interactive():
    provider = SimpleNamespace(descriptor=ProviderDescriptor('stub'), url='https://example.test', team=None)
    with pytest.raises(TypeError, match='stub does not provide templates'):
        Application(config_for('slack'), {'default': {'id': 'C1'}}, 'default', provider=provider)


@pytest.mark.asyncio
@pytest.mark.parametrize('provider_id', ['slack', 'mattermost', 'telegram', 'none'])
async def test_registry_facade_initialization_delivery_and_cleanup(provider_id, runtime):
    config = config_for(provider_id)
    app = get_application(config, {k: v.model_dump() if hasattr(v, 'model_dump') else v for k, v in config.channels.items()}, 'default')
    assert type(app) is Application
    assert get_provider_registry().resolve(provider_id).descriptor == app.provider.descriptor
    assert isinstance(app.provider, MessengerProvider)
    assert not isinstance(app.provider, Application)
    transport = Transport()
    app._setup_http = Mock(return_value=transport)
    await app.initialize_async()
    assert isinstance(app.users, UserManager)
    if provider_id == 'none':
        app._setup_http.assert_not_called()
    else:
        assert app.provider.http is transport
        assert not hasattr(app.provider, 'users')
        assert not hasattr(app.provider, 'chains')
        user = await app.get_user_details(123 if provider_id == 'telegram' else 'U1')
        assert user['exists'] and user['username'] == 'alice'
    incident = incident_for(provider_id)
    incident.ts = await app.create_incident_message(incident, 'body', 'header', '5312241539987020022')
    assert incident.ts
    if provider_id == 'telegram':
        assert incident.ts == '10/20'
        assert transport.calls[0][1].endswith('/setWebhook')
    app.form_body_header_status_icons = Mock(return_value=('body', 'header', '5312241539987020022'))
    await app.update_incident_message(incident)
    assert await app._post_notification(incident, 'header', 'notice') == 200
    if provider_id != 'none':
        payload = transport.calls[-1][2]['json']
        text = payload.get('text', payload.get('message'))
        assert text == ('notice' if provider_id == 'telegram' else 'header\nnotice')
        assert all(response.closed for response in transport.responses)
    await app.close()
    assert transport.closed == (provider_id != 'none')


@pytest.mark.asyncio
@pytest.mark.parametrize('provider_id', ['slack', 'mattermost', 'telegram'])
async def test_callbacks_use_facade_state_and_preserve_assignment(provider_id, runtime):
    user_id = 123 if provider_id == 'telegram' else 'U1'
    config = config_for(provider_id, users={'alice': {'id': user_id}})
    app = get_application(config, {'default': {'id': 'C1'}}, 'default')
    transport = Transport()
    app._setup_http = Mock(return_value=transport)
    await app.initialize_async()
    incident = incident_for(provider_id)
    incident.ts = '10/20' if provider_id == 'telegram' else '123.456'
    incidents = Mock(get_by_ts=Mock(return_value=incident))
    queue = Mock(delete_by_id=AsyncMock())
    app.post_assignment_notification = AsyncMock()
    app.form_body_header_status_icons = Mock(return_value=('body', 'header', '5312241539987020022'))
    if provider_id == 'slack':
        payload = {'token': 'verify', 'message_ts': incident.ts, 'user': {'id': user_id},
                   'actions': [{'name': 'chain'}], 'original_message': {'text': 'old'}}
    elif provider_id == 'mattermost':
        payload = {'post_id': incident.ts, 'user_id': user_id, 'context': {'action': 'chain'}}
    else:
        payload = {'callback_query': {'id': 'ack-1', 'data': 'stop_chain', 'from': {'id': user_id},
                                     'message': {'message_id': 20, 'message_thread_id': 10}}}
    if provider_id == 'slack':
        payload = interaction_request(payload)
    else:
        payload = json_request(payload)
    response = await app.buttons_handler(payload, incidents, queue)
    assert response.status_code == 200
    assert incident.assigned_user_id == user_id
    assert incident.chain_enabled is False
    incident.dump.assert_called_once_with()
    queue.delete_by_id.assert_awaited_once_with('incident-1', delete_steps=True, delete_status=False)
    import asyncio
    await asyncio.gather(*app._async_tasks)
    app.post_assignment_notification.assert_awaited_once_with(incident)
    await app.close()


@pytest.mark.asyncio
async def test_take_it_loads_uncached_user_from_messenger(runtime, monkeypatch):
    store = Mock()
    store.get_all_users_by_type.return_value = {}
    monkeypatch.setattr('app.im.application.get_user_store', lambda: store)
    user_id = 't9z54i9h9ffszqhoiiqwp5emhw'
    app = get_application(config_for('mattermost'), {'default': {'id': 'C1'}}, 'default')
    transport = Transport()
    app._setup_http = Mock(return_value=transport)
    await app.initialize_async()
    incident = incident_for('mattermost')
    incident.ts = 'post-1'
    app.post_assignment_notification = AsyncMock()
    app.form_body_header_status_icons = Mock(return_value=('body', 'header', ':firing:'))
    response = await app.buttons_handler(
        json_request({'post_id': incident.ts, 'user_id': user_id, 'context': {'action': 'chain'}}),
        Mock(get_by_ts=Mock(return_value=incident)),
        Mock(delete_by_id=AsyncMock()),
    )
    assert response.status_code == 200
    assert incident.assigned_user_id == user_id
    assert incident.assigned_user == 'alice'
    assert incident.assigned_fullname == 'Alice'
    assert app.users.get_user_by_id(user_id).exists
    store.save.assert_called_once()
    assert store.save.call_args.args[0] == user_id
    user_gets = [url for method, url, _ in transport.calls if '/api/v4/users/' in url]
    assert user_gets == [f'https://mm.test/api/v4/users/{user_id}?user_id={user_id}']
    await app.fetch_and_assign_user_name(incident, user_id, dump=False)
    user_gets = [url for method, url, _ in transport.calls if '/api/v4/users/' in url]
    assert len(user_gets) == 1
    await app.close()


@pytest.mark.asyncio
async def test_assignment_skips_unknown_and_unreachable_users(runtime):
    app = get_application(config_for('mattermost'), {'default': {'id': 'C1'}}, 'default')
    app._setup_http = Mock(return_value=Transport())
    await app.initialize_async()
    incident = incident_for('mattermost')
    app.provider.fetch_user = AsyncMock(return_value=UserProfile(id='missing', exists=False))
    await app.fetch_and_assign_user_name(incident, 'missing', dump=False)
    assert incident.assigned_user_id == ''
    app.provider.fetch_user = AsyncMock(side_effect=asyncio.TimeoutError)
    await app.fetch_and_assign_user_name(incident, 'missing', dump=False)
    assert incident.assigned_user_id == ''
    await app.close()


@pytest.mark.asyncio
async def test_none_keeps_manual_freeze_a_noop(runtime):
    config = config_for('none')
    app = get_application(config, {'default': {'id': ''}}, 'default')
    incident = Mock()
    await app.handle_ui_freeze(incident, 'tomorrow', 'U1', Mock())
    incident.freeze.assert_not_called()


def test_presentation_is_detached_and_immutable():
    incident = incident_for('slack')
    incident.frozen_until = datetime(2026, 1, 1, tzinfo=timezone.utc)
    message = Application._presentation(incident, 'body', 'header', 'icon', 'UTC')
    incident.status = 'closed'
    assert message.status == 'firing'
    assert message.frozen_until == '2026-01-01T00:00:00+00:00'
    assert not hasattr(message, 'dump')
    with pytest.raises(FrozenInstanceError):
        message.status = 'resolved'


def test_registry_rejects_missing_duplicate_and_incompatible_providers():
    registry = ProviderRegistry()
    registered = get_provider_registry().resolve('slack')
    with pytest.raises(ValueError, match='not registered'):
        registry.resolve('slack')
    registry.register(registered)
    with pytest.raises(ValueError, match='Duplicate'):
        registry.register(registered)
    with pytest.raises(ValueError, match='Incompatible'):
        registry.register(replace(registered, descriptor=ProviderDescriptor('new', api_version=2)))


def test_contract_does_not_import_core_or_external_runtime():
    import impulse_messenger_api as api

    paths = tuple(Path(api.__file__).parent.rglob('*.py'))
    assert paths
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.ImportFrom):
                if node.level:
                    continue
                modules = [node.module or '']
            elif isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            else:
                continue
            for module in modules:
                assert module.split('.')[0] in sys.stdlib_module_names | {'pydantic', 'impulse_messenger_api'}, (path, module)


def test_external_provider_import_boundaries_and_core_selection():
    app_root = Path(__file__).resolve().parents[2] / 'app'
    provider_ids = ('slack', 'mattermost', 'telegram')
    namespaces = tuple(f'impulse_{provider_id}' for provider_id in provider_ids)
    for namespace in namespaces:
        provider_root = Path(import_module(namespace).__file__).parent
        paths = tuple(provider_root.rglob('*.py'))
        assert paths, namespace
        for path in paths:
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node, ast.ImportFrom):
                    modules = [node.module or ''] if not node.level else []
                elif isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                else:
                    continue
                for module in modules:
                    assert module != 'app' and not module.startswith('app.'), (path, module)
                    assert not any(module == other or module.startswith(other + '.')
                                   for other in namespaces if other != namespace), (path, module)

    assert all(not (app_root / 'im' / 'providers' / provider_id).exists() for provider_id in provider_ids)
    for path in app_root.rglob('*.py'):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.ImportFrom):
                modules = [node.module or '']
            elif isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            else:
                modules = []
            assert not any(module == namespace or module.startswith(namespace + '.')
                           for module in modules for namespace in namespaces), path
            if isinstance(node, ast.Compare):
                assert not any(
                    (isinstance(item, ast.Constant) and item.value in provider_ids)
                    or (isinstance(item, ast.Attribute) and item.attr in ('SLACK', 'MATTERMOST', 'TELEGRAM'))
                    for item in ast.walk(node)
                ), path


@pytest.mark.asyncio
async def test_slack_callback_rejects_invalid_token_before_lookup(runtime):
    config = config_for('slack')
    app = get_application(config, {'default': {'id': 'C1'}}, 'default')
    incidents = Mock()
    response = await app.buttons_handler(interaction_request({'token': 'wrong'}), incidents, Mock())
    assert response.status_code == 401
    incidents.get_by_ts.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('provider_id', ['slack', 'mattermost', 'telegram'])
async def test_blocked_callbacks_do_not_assign_or_schedule(provider_id, runtime):
    config = config_for(provider_id)
    app = get_application(config, {'default': {'id': 'C1'}}, 'default')
    app._setup_http = Mock(return_value=Transport())
    await app.initialize_async()
    incident = incident_for(provider_id)
    incident.ts = '10/20' if provider_id == 'telegram' else '123.456'
    incident.is_frozen = incident.frozen_by_inhibition = True
    app.form_body_header_status_icons = Mock(return_value=('body', 'header', 'icon'))
    if provider_id == 'slack':
        payload = {'token': 'verify', 'message_ts': incident.ts, 'user': {'id': 'U1'},
                   'actions': [{'name': 'chain'}], 'original_message': {'text': 'old'}}
    elif provider_id == 'mattermost':
        payload = {'post_id': incident.ts, 'user_id': 'U1', 'context': {'action': 'chain'}}
    else:
        payload = {'callback_query': {'id': 'ack-1', 'data': 'stop_chain', 'from': {'id': 123},
                                     'message': {'message_id': 20, 'message_thread_id': 10}}}
    queue = Mock(delete_by_id=AsyncMock())
    if provider_id == 'slack':
        payload = interaction_request(payload)
    else:
        payload = json_request(payload)
    response = await app.buttons_handler(payload, Mock(get_by_ts=Mock(return_value=incident)), queue)
    assert response.status_code == 200
    assert incident.assigned_user_id == ''
    queue.delete_by_id.assert_not_called()
    assert not app._async_tasks
    assert all(response.closed for response in app.http.responses)
    await app.close()


@pytest.mark.asyncio
async def test_telegram_freeze_menu_uses_facade_renderer_and_closes_ack(runtime):
    config = config_for('telegram')
    app = get_application(config, {'default': {'id': -100123}}, 'default')
    transport = Transport()
    app._setup_http = Mock(return_value=transport)
    await app.initialize_async()
    app.form_body_header_status_icons = Mock(return_value=('body', 'header', '5312241539987020022'))
    incident = incident_for('telegram')
    incident.ts = '10/20'
    payload = {'callback_query': {'id': 'ack-menu', 'data': 'freeze_menu', 'from': {'id': 123},
                                 'message': {'message_id': 20, 'message_thread_id': 10}}}
    response = await app.buttons_handler(json_request(payload), Mock(get_by_ts=Mock(return_value=incident)), Mock())
    assert response.status_code == 200
    edit, ack = transport.calls[-2:]
    assert edit[1].endswith('/editMessageText')
    assert edit[2]['json']['reply_markup']['inline_keyboard'][-1][0]['callback_data'] == 'freeze_back'
    assert ack[2]['json'] == {'callback_query_id': 'ack-menu'}
    assert all(response.closed for response in transport.responses)
    incident.dump.assert_not_called()
    await app.close()


@pytest.mark.asyncio
async def test_telegram_freeze_menu_unfreezes_instead_of_opening_options(runtime):
    config = config_for('telegram')
    app = get_application(config, {'default': {'id': -100123}}, 'default')
    transport = Transport()
    app._setup_http = Mock(return_value=transport)
    await app.initialize_async()
    app.form_body_header_status_icons = Mock(return_value=('body', 'header', '5312241539987020022'))

    class TimeFrozenIncident:
        channel_id = -100123
        ts = '10/20'
        status = 'firing'
        chain_enabled = True
        parents = []
        frozen_until = datetime.now(timezone.utc)
        frozen_until_source = 'time'
        task_link = ''
        assigned_user_id = ''
        payload = {}
        uniq_id = 'incident-1'
        chain_active_seconds = 0
        status_update_datetime = datetime.now(timezone.utc)
        dump = Mock()

        @property
        def is_frozen(self):
            return self.frozen_until is not None or len(self.parents) > 0

        @property
        def frozen_by_inhibition(self):
            return False

        @property
        def frozen_by_maintenance(self):
            return False

        def can_manual_unfreeze(self):
            return self.frozen_until is not None and self.frozen_until_source == 'time' and not self.parents

        def unfreeze(self):
            self.frozen_until = None
            self.frozen_until_source = None
            self.parents = []
            self.dump()

        def get_chain(self):
            return []

    incident = TimeFrozenIncident()
    queue = Mock(delete_by_id_and_type=AsyncMock(), put_first=AsyncMock(), recreate=AsyncMock(), put=AsyncMock())
    payload = {'callback_query': {'id': 'ack-unfreeze', 'data': 'freeze_menu', 'from': {'id': 123},
                                 'message': {'message_id': 20, 'message_thread_id': 10, 'chat': {'id': -100123}}}}
    response = await app.buttons_handler(json_request(payload), Mock(get_by_ts=Mock(return_value=incident)), queue)
    assert response.status_code == 200
    assert incident.frozen_until is None
    edit = next(call for call in reversed(transport.calls) if call[1].endswith('/editMessageText'))
    keyboard = edit[2]['json']['reply_markup']['inline_keyboard']
    assert keyboard[0][1]['callback_data'] == 'freeze_menu'
    assert all(button['callback_data'] != 'freeze_back' for row in keyboard for button in row)
    assert transport.calls[-1][2]['json'] == {'callback_query_id': 'ack-unfreeze'}
    await app.close()


@pytest.mark.parametrize('provider_id', ['slack', 'mattermost', 'telegram'])
def test_custom_template_override_keeps_precedence(provider_id, runtime, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    implicit = tmp_path / 'templates' / f'{provider_id}_body.j2'
    implicit.mkdir(parents=True)
    template = tmp_path / 'custom.j2'
    template.write_text('custom body')
    get_provider_registry.cache_clear()
    config = config_for(provider_id, template_files={'body': str(template)})
    app = get_application(config, {'default': {'id': 'C1'}}, 'default')
    assert app.body_template.form_message({}, {}) == 'custom body'


@pytest.mark.parametrize('provider_id, expected', [
    ('slack', 'https://public.test/team/U1'),
    ('mattermost', 'https://public.test/my-team/users/U1'),
    ('telegram', 'https://t.me/alice'),
])
def test_user_links_honor_supplied_identity(provider_id, expected, runtime):
    provider = get_application(config_for(provider_id), {'default': {'id': 'C1'}}, 'default').provider
    assert provider.user_url(UserProfile('U1', True, username='alice'),
                             ProviderIdentity('https://public.test', 'my-team')) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize('provider_id', ['slack', 'mattermost', 'telegram'])
async def test_provider_releases_response_when_user_json_is_invalid(provider_id, runtime):
    provider = get_application(config_for(provider_id), {'default': {'id': 'C1'}}, 'default').provider
    response = Response({})
    response.json = AsyncMock(side_effect=ValueError('invalid JSON'))
    provider.http = Mock(get=AsyncMock(return_value=response))
    with pytest.raises(ValueError, match='invalid JSON'):
        await provider.fetch_user(123 if provider_id == 'telegram' else 'U1')
    assert response.closed


REQUIRED_TEMPLATE_NAMES = (
    'body', 'header', 'status_icons', 'chain_step_user', 'chain_step_user_group',
    'chain_step_group', 'chain_step_webhook', 'incident_notifications_assignment',
    'incident_notifications_status_update', 'incident_notifications_new_firing',
    'incident_notifications_partial_resolved', 'incident_notifications_freeze',
    'incident_notifications_unfreeze',
)


@pytest.mark.asyncio
@pytest.mark.parametrize('provider_id', ['mattermost', 'telegram'])
@pytest.mark.parametrize('names, expected', [
    ({'first_name': 'Alice', 'last_name': 'Smith'}, 'Alice Smith'),
    ({'first_name': 'Alice'}, 'Alice'),
    ({'last_name': 'Smith'}, 'Smith'),
    ({}, ''),
    ({'first_name': ' Alice ', 'last_name': ' Smith '}, 'Alice   Smith'),
])
async def test_full_name_preserves_name_parts_and_trims_outer_whitespace(provider_id, names, expected):
    registration = get_provider_registry().resolve(provider_id)
    provider = registration.factory(config_for(provider_id), {
        'MATTERMOST_ACCESS_TOKEN': 'token', 'TELEGRAM_BOT_TOKEN': 'token',
    })
    response = Response({'ok': True, 'result': names} if provider_id == 'telegram' else names)
    transport = Mock(get=AsyncMock(return_value=response))
    await provider.initialize(ProviderContext(transport, 'http://impulse.test/app'))
    user = await provider.fetch_user(123 if provider_id == 'telegram' else 'U1')
    assert user.full_name == expected
    assert response.closed


@pytest.mark.parametrize('provider_id', ['slack', 'mattermost', 'telegram'])
def test_same_directory_template_overrides(provider_id, runtime, tmp_path, monkeypatch):
    from app.im.template import ProviderTemplates

    monkeypatch.chdir(tmp_path)
    for name in REQUIRED_TEMPLATE_NAMES:
        directory = 'templates' if name in ('body', 'header', 'status_icons') else 'thread_templates'
        path = tmp_path / directory / f'{provider_id}_{name}.j2'
        path.parent.mkdir(exist_ok=True)
        path.write_text(provider_id + ':' + name + ' {{ value }}', encoding='utf-8')

    app = get_application(config_for(provider_id), {'default': {'id': 'C1'}}, 'default')
    for name in REQUIRED_TEMPLATE_NAMES:
        expected = provider_id + ':' + name + ' ☕'
        if name in ('body', 'header', 'status_icons'):
            actual = getattr(app, name + '_template').render(value='☕')
        else:
            source = ProviderTemplates(name)[provider_id]
            actual = app.notification_template(source).form_notification(value='☕')
        assert actual == expected


@pytest.mark.parametrize('provider_id', ['slack', 'mattermost', 'telegram'])
@pytest.mark.parametrize('name', ['body', 'chain_step_user'])
def test_existing_template_read_errors_do_not_use_packaged_defaults(provider_id, name, runtime, tmp_path, monkeypatch):
    from app.im.template import ProviderTemplates

    monkeypatch.chdir(tmp_path)
    directory = 'templates' if name == 'body' else 'thread_templates'
    (tmp_path / directory / f'{provider_id}_{name}.j2').mkdir(parents=True)
    with pytest.raises(IsADirectoryError):
        if name == 'body':
            get_application(config_for(provider_id), {'default': {'id': 'C1'}}, 'default')
        else:
            ProviderTemplates(name)[provider_id]


@pytest.mark.parametrize('provider_id', ['slack', 'mattermost', 'telegram', 'none'])
def test_builtin_registration_satisfies_public_contract(provider_id):
    registration = get_provider_registry().resolve(provider_id)
    descriptor = registration.descriptor
    assert descriptor.provider_id == provider_id
    assert descriptor.api_version == PLUGIN_API_VERSION
    assert descriptor.rate_window_seconds > 0
    assert registration.config_model is registration.factory.config_model

    if provider_id == 'none':
        assert not descriptor.messaging_enabled
        assert registration.template_source is None
        assert isinstance(registration.factory(config_for(provider_id), {}), MessengerProvider)
        return

    from jinja2 import Environment

    assert descriptor.messaging_enabled
    assert descriptor.rate_limit is not None and descriptor.rate_limit > 0
    assert isinstance(registration.factory(config_for(provider_id), {
        'SLACK_BOT_USER_OAUTH_TOKEN': 'token', 'SLACK_VERIFICATION_TOKEN': 'verify',
        'MATTERMOST_ACCESS_TOKEN': 'token', 'TELEGRAM_BOT_TOKEN': 'token',
    }), InteractiveProvider)
    for name in REQUIRED_TEMPLATE_NAMES:
        source = registration.template_source(name)
        assert source.strip(), (provider_id, name)
        Environment().parse(source)
    with pytest.raises(KeyError):
        registration.template_source('not_a_template')


@pytest.mark.parametrize('provider_id, secret_name', [
    ('slack', 'SLACK_BOT_USER_OAUTH_TOKEN'),
    ('mattermost', 'MATTERMOST_ACCESS_TOKEN'),
    ('telegram', 'TELEGRAM_BOT_TOKEN'),
])
def test_builtin_missing_secret_names_only_the_required_variable(provider_id, secret_name):
    registration = get_provider_registry().resolve(provider_id)
    with pytest.raises(ValueError) as error:
        registration.factory(config_for(provider_id), {'DEV_MESSENGER_CUSTOM_ADDRESS': 'fixture-secret-value'})
    assert secret_name in str(error.value)
    assert 'fixture-secret-value' not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize('provider_id, expected', [
    ('slack', ('Alice', 'alice', 'UTC', (GroupProfile('G1', 'group'),))),
    ('mattermost', ('Alice', 'alice', 'UTC', (GroupProfile('G1', 'group'),))),
    ('telegram', ('Alice', 'alice', None, ())),
    ('none', (None, None, None, ())),
])
async def test_builtin_profiles_are_normalized_and_responses_closed(provider_id, expected):
    config = config_for(provider_id, groups={'group': {'id': 'G1'}}) if provider_id in ('slack', 'mattermost') else config_for(provider_id)
    registration = get_provider_registry().resolve(provider_id)
    provider = registration.factory(config, {
        'SLACK_BOT_USER_OAUTH_TOKEN': 'token', 'SLACK_VERIFICATION_TOKEN': 'verify',
        'MATTERMOST_ACCESS_TOKEN': 'token', 'TELEGRAM_BOT_TOKEN': 'token',
    })
    transport = Transport()
    await provider.initialize(ProviderContext(transport, 'http://impulse.test/app'))
    user = await provider.fetch_user(123 if provider_id == 'telegram' else 'U1')
    groups = await provider.fetch_groups()
    assert isinstance(user, UserProfile)
    assert (user.full_name, user.username, user.timezone, groups) == expected
    assert user.exists == (provider_id != 'none')
    assert all(response.closed for response in transport.responses)


@pytest.mark.asyncio
@pytest.mark.parametrize('provider_id', ['slack', 'mattermost', 'telegram'])
async def test_builtin_malformed_callbacks_return_provider_errors(provider_id):
    provider = get_provider_registry().resolve(provider_id).factory(config_for(provider_id), {
        'SLACK_BOT_USER_OAUTH_TOKEN': 'token', 'SLACK_VERIFICATION_TOKEN': 'verify',
        'MATTERMOST_ACCESS_TOKEN': 'token', 'TELEGRAM_BOT_TOKEN': 'token',
    })
    response = await provider.parse_interaction(InteractionRequest('POST', (), (), b'{malformed'))
    assert isinstance(response, ProviderResponse)
    assert response.status_code == 400


@pytest.mark.parametrize('provider_id, message, identity, expected', [
    ('slack', MessageRef('C1', '123.456'), ProviderIdentity('https://workspace.slack.test'),
     'https://workspace.slack.test/archives/C1/p123456'),
    ('mattermost', MessageRef('C1', 'post-1'), ProviderIdentity('https://mm.test', 'Test-Team'),
     'https://mm.test/test-team/pl/post-1'),
    ('telegram', MessageRef(-100123, '10/20'), ProviderIdentity('https://api.telegram.org'),
     'https://t.me/c/123/10/20'),
])
def test_builtin_incident_links_use_public_message_references(provider_id, message, identity, expected):
    registration = get_provider_registry().resolve(provider_id)
    assert registration.incident_url(message, identity) == expected


@pytest.mark.asyncio
async def test_telegram_transport_error_redacts_custom_provider_url(runtime, monkeypatch):
    monkeypatch.setenv('DEV_MESSENGER_CUSTOM_ADDRESS', 'http://fake/custom')
    app = get_application(config_for('telegram'), {'default': {'id': -100123}}, 'default')
    client = app._setup_http()
    try:
        with patch.object(client._client, 'request', new=AsyncMock(
            side_effect=asyncio.TimeoutError(f'failed request to {app.provider.url}/getChat'))):
            with patch('app.http_client.rate_limited_client.logger') as logger:
                with pytest.raises(asyncio.TimeoutError):
                    await client.get(f'{app.provider.url}/getChat')
        extra = logger.error.call_args.kwargs['extra']
        assert 'test-token' not in extra['url']
        assert 'test-token' not in extra['detail']
    finally:
        await client.close()
