"""Exercise the production composition root, not the legacy subclass constructors."""

import ast
import json
from urllib.parse import urlencode
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.config.environment import EnvironmentConfig
from app.config.validation import MattermostApplicationConfig, NullApplicationConfig, TelegramApplicationConfig
from app.im.providers.slack.config import SlackApplicationConfig
from app.im.application import Application
from app.im.helpers import get_application
from app.im.plugin_api import (
    MessengerProvider, ProviderDescriptor, ProviderIdentity, UserProfile, InteractionRequest,
)
from app.im.registry import ProviderRegistry, get_provider_registry
from app.im.users import UserManager


def interaction_request(payload):
    return InteractionRequest('POST', (), (), urlencode({'payload': json.dumps(payload)}).encode())


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
    monkeypatch.setenv('SLACK_VERIFICATION_TOKEN', 'verify')
    env = EnvironmentConfig(mattermost_access_token='test-token', telegram_bot_token='test-token')
    for module in ('app.im.providers.mattermost', 'app.im.providers.telegram', 'app.im.mattermost.threads'):
        monkeypatch.setattr(module + '.get_environment_config', lambda: env)
    config = SimpleNamespace(app=SimpleNamespace(task_management=None, general=SimpleNamespace(timezone='UTC')),
                             messenger=SimpleNamespace(impulse_address='http://impulse.test'))
    for module in ('app.im.application', 'app.im.providers.telegram', 'app.im.mattermost.threads'):
        monkeypatch.setattr(module + '.get_config', lambda: config)
    store = Mock()
    store.get_all_users_by_type.return_value = {}
    monkeypatch.setattr('app.im.application.get_user_store', lambda: store)
    return config


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
        user = await app.get_user_details({'id': 123 if provider_id == 'telegram' else 'U1'})
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
    response = await app.buttons_handler(payload, incidents, queue, Mock())
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
async def test_none_keeps_manual_freeze_a_noop(runtime):
    config = config_for('none')
    app = get_application(config, {'default': {'id': ''}}, 'default')
    incident = Mock()
    await app.handle_ui_freeze(incident, 'tomorrow', 'U1', Mock(), Mock())
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
    import app.im.plugin_api as api
    tree = ast.parse(Path(api.__file__).read_text())
    imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert set(imports) <= {'dataclasses', 'typing', 'enum', 'collections.abc', 'app.im.plugin_config'}
    forbidden = ('app.incident', 'app.queue', 'app.route', 'app.maintenance', 'app.inhibition', 'app.http_client')
    for path in (Path(api.__file__).parent / 'providers').glob('*.py'):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names = [node.module or ''] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names] if isinstance(node, ast.Import) else []
            assert not any(name.startswith(forbidden) for name in names), path


@pytest.mark.asyncio
async def test_slack_callback_rejects_invalid_token_before_lookup(runtime):
    config = config_for('slack')
    app = get_application(config, {'default': {'id': 'C1'}}, 'default')
    incidents = Mock()
    response = await app.buttons_handler(interaction_request({'token': 'wrong'}), incidents, Mock(), Mock())
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
    response = await app.buttons_handler(interaction_request(payload) if provider_id == 'slack' else payload, Mock(get_by_ts=Mock(return_value=incident)), queue, Mock())
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
    response = await app.buttons_handler(payload, Mock(get_by_ts=Mock(return_value=incident)), Mock(), Mock())
    assert response.status_code == 200
    edit, ack = transport.calls[-2:]
    assert edit[1].endswith('/editMessageText')
    assert edit[2]['json']['reply_markup']['inline_keyboard'][-1][0]['callback_data'] == 'freeze_back'
    assert ack[2]['json'] == {'callback_query_id': 'ack-menu'}
    assert all(response.closed for response in transport.responses)
    incident.dump.assert_not_called()
    await app.close()


@pytest.mark.parametrize('provider_id', ['slack', 'mattermost', 'telegram'])
def test_custom_template_override_keeps_precedence(provider_id, runtime, tmp_path):
    template = tmp_path / 'custom.j2'
    template.write_text('custom body')
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
