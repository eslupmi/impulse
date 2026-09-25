"""Focused Phase 2 contract and HTTP regression evidence (all messenger APIs mocked)."""

import ast
import hashlib
import hmac
from importlib.util import resolve_name
import json
import os
import subprocess
import sys
import time
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config.validation import ImpulseConfig
from app.im.application import Application
from app.im.helpers import get_application
from app.im.plugin_api import Interaction, InteractionAction, InteractionRequest, ProviderResponse
from app.im.providers.slack import SlackProvider, TEMPLATE_NAMES
from app.im.providers.slack.config import SlackApplicationConfig
from app.im.registry import get_provider_registry
from app.routes import create_router
from tests.test_im.test_provider_seam import Transport, config_for, incident_for, runtime  # noqa: F401
from tests.test_im.test_slack.test_slack_application import make_provider


def callback(**updates):
    return {
        'token': 'verify',
        'message_ts': '123.456',
        'channel': {'id': 'C1'},
        'user': {'id': 'U1'},
        'actions': [{'name': 'chain'}],
        'original_message': {'text': 'original'},
        **updates,
    }


def request(payload, headers=()):
    return InteractionRequest('POST', headers, (), urlencode({'payload': json.dumps(payload)}).encode())


@pytest.mark.parametrize('missing', ['SLACK_BOT_USER_OAUTH_TOKEN', 'SLACK_VERIFICATION_TOKEN'])
def test_missing_secrets_are_named_without_values(missing):
    with pytest.raises(ValueError) as error:
        make_provider(**{missing: ''})
    assert missing in str(error.value)
    assert 'test-token' not in str(error.value)
    assert 'verify' not in str(error.value)


def test_registered_config_preserves_channels_users_groups_and_common_validation():
    raw = {
        'messenger': config_for('slack', users={'alice': {'id': 'U1'}}, groups={'ops': {'id': 'G1'}}).model_dump(),
        'route': {'channel': 'default'},
    }
    config = ImpulseConfig.model_validate(raw)
    assert isinstance(config.messenger, SlackApplicationConfig)
    assert config.messenger.users['alice'].id == 'U1'
    assert config.messenger.groups['ops'].id == 'G1'
    raw['route']['channel'] = 'missing'
    with pytest.raises(ValidationError, match='not found in messenger channels'):
        ImpulseConfig.model_validate(raw)
    raw['messenger']['type'] = 'unregistered'
    with pytest.raises(ValidationError, match='not registered'):
        ImpulseConfig.model_validate(raw)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'actions,expected',
    [
        ([{'name': 'chain'}, {'name': 'task'}], [InteractionAction.TOGGLE_ASSIGNMENT, InteractionAction.CREATE_TASK]),
        (
            [{'name': 'freeze', 'type': 'select', 'selected_options': [{'value': 'tomorrow'}]}],
            [InteractionAction.FREEZE],
        ),
        ([{'name': 'freeze', 'type': 'button'}], [InteractionAction.FREEZE]),
        ([{'name': 'unsupported'}], [InteractionAction.NOOP]),
    ],
)
async def test_callback_becomes_immutable_ordered_commands(actions, expected):
    payload = callback(actions=actions)
    parsed = await make_provider().parse_interaction(request(payload))
    assert isinstance(parsed, Interaction)
    assert [c.action for c in parsed.commands] == expected
    assert parsed.message.channel_id == 'C1'
    payload['original_message']['text'] = 'mutated'
    assert json.loads(parsed.original_response.body)['text'] == 'original'
    with pytest.raises(FrozenInstanceError):
        parsed.actor_id = 'U2'


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'body,status',
    [
        (b'payload=not-json', 400),
        (b'payload=[]', 400),
        (b'{}', 400),
        (urlencode({'payload': json.dumps(callback(token='wrong'))}).encode(), 401),
        (
            urlencode(
                {
                    'payload': json.dumps(
                        callback(
                            actions=[{'name': 'freeze', 'type': 'select', 'selected_options': [{'value': 'invalid'}]}]
                        )
                    )
                }
            ).encode(),
            400,
        ),
        (urlencode({'payload': json.dumps(callback(actions=[None]))}).encode(), 400),
        (urlencode({'payload': json.dumps(callback(user=None))}).encode(), 400),
    ],
)
async def test_invalid_callbacks_fail_before_business_lookup(body, status, runtime):
    app = get_application(config_for('slack'), {'default': {'id': 'C1'}}, 'default')
    incidents = Mock()
    response = await app.buttons_handler(InteractionRequest('POST', (), (), body), incidents, Mock(), Mock())
    assert response.status_code == status
    incidents.get_by_ts.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'offset,tamper,valid', [(0, False, True), (-301, False, False), (301, False, False), (0, True, False)]
)
async def test_signed_callback_verifies_exact_body_and_freshness(offset, tamper, valid):
    provider = make_provider(SLACK_SIGNING_SECRET='signing-key')
    req = request(callback(token='wrong'))
    timestamp = str(int(time.time()) + offset)
    signature = (
        'v0=' + hmac.new(b'signing-key', b'v0:' + timestamp.encode() + b':' + req.body, hashlib.sha256).hexdigest()
    )
    req = replace(req, headers=(('X-Slack-Request-Timestamp', timestamp), ('X-Slack-Signature', signature)))
    if tamper:
        req = replace(req, body=req.body + b' ')
    result = await provider.parse_interaction(req)
    assert isinstance(result, Interaction) is valid
    if not valid:
        assert result.status_code == 401


@pytest.mark.asyncio
async def test_signing_secret_disallows_unsigned_token_fallback():
    result = await make_provider(SLACK_SIGNING_SECRET='key').parse_interaction(request(callback()))
    assert result.status_code == 401


def test_http_route_passes_raw_bytes_to_provider_and_returns_ack(runtime):
    messenger = get_application(config_for('slack'), {'default': {'id': 'C1'}}, 'default')
    app = FastAPI()
    app.state.messenger = messenger
    app.state.incidents = Mock(get_by_ts=Mock(return_value=None))
    app.state.queue = Mock()
    app.state.route = Mock()
    app.include_router(create_router(''))
    with TestClient(app) as client:
        result = client.post(
            '/app', content=request(callback()).body, headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        assert result.status_code == 200
        assert result.json() == {'text': 'original'}
        result = client.post(
            '/app', content=b'payload=broken', headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        assert result.status_code == 400
    app.state.incidents.get_by_ts.assert_called_once_with(ts='123.456')


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['missing', 'wrong-channel', 'inhibited', 'maintenance', 'time'])
async def test_blocked_or_missing_incidents_never_change_queue(kind, runtime):
    app = get_application(config_for('slack'), {'default': {'id': 'C1'}}, 'default')
    incident = incident_for('slack')
    incident.ts = '123.456'
    incident.is_frozen = kind in {'inhibited', 'maintenance', 'time'}
    incident.frozen_by_inhibition = kind == 'inhibited'
    incident.frozen_by_maintenance = kind == 'maintenance'
    if kind == 'wrong-channel':
        incident.channel_id = 'C2'
    incidents = Mock(get_by_ts=Mock(return_value=None if kind == 'missing' else incident))
    queue = Mock(delete_by_id=AsyncMock())
    result = await app.buttons_handler(request(callback()), incidents, queue, Mock())
    assert json.loads(result.body) == {'text': 'original'}
    queue.delete_by_id.assert_not_called()
    incident.dump.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('option', ['tomorrow', 'next_monday', 'month', '6months'])
async def test_freeze_option_and_timezone_reach_core_only_after_verification(option, runtime):
    app = get_application(config_for('slack'), {'default': {'id': 'C1'}}, 'default')
    incident = incident_for('slack')
    incident.ts = '123.456'
    app._handle_freeze_action = AsyncMock()
    app._get_user_timezone_str = Mock(return_value='Europe/Berlin')
    app.form_body_header_status_icons = Mock(return_value=('body', 'header', 'icon'))
    incidents = Mock(get_by_ts=Mock(return_value=incident))
    queue = Mock()
    result = await app.buttons_handler(
        request(callback(actions=[{'name': 'freeze', 'type': 'select', 'selected_options': [{'value': option}]}])),
        incidents,
        queue,
        Mock(),
    )
    app._handle_freeze_action.assert_awaited_once_with(
        incident, option, 'U1', incidents, queue, user_timezone='Europe/Berlin'
    )
    assert result.status_code == 200
    assert json.loads(result.body)['ts'] == incident.ts


@pytest.mark.asyncio
async def test_manual_unfreeze_and_resolved_release_use_core_actions(runtime):
    app = get_application(config_for('slack'), {'default': {'id': 'C1'}}, 'default')
    incident = incident_for('slack')
    incident.ts = '123.456'
    incident.is_frozen = True
    incident.can_manual_unfreeze = lambda: True
    app._handle_unfreeze_action = AsyncMock()
    app.form_body_header_status_icons = Mock(return_value=('body', 'header', 'icon'))
    incidents = Mock(get_by_ts=Mock(return_value=incident))
    queue = Mock(delete_by_id=AsyncMock())
    await app.buttons_handler(
        request(callback(actions=[{'name': 'freeze', 'type': 'button'}])), incidents, queue, Mock()
    )
    app._handle_unfreeze_action.assert_awaited_once_with(incident, 'U1', queue)
    incident.is_frozen = False
    incident.chain_enabled = False
    incident.status = 'resolved'
    app.post_unassignment_notification = AsyncMock()
    await app.buttons_handler(request(callback()), incidents, queue, Mock())
    import asyncio

    await asyncio.gather(*app._async_tasks)
    incident.release.assert_called_once()
    app.post_unassignment_notification.assert_awaited_once_with(incident)


def test_resources_and_imports_work_without_core_or_checkout_cwd(tmp_path):
    root = Path(__file__).resolve().parents[3]
    script = """
import sys
class NoPrivateCore:
    def find_spec(self, fullname, *args):
        if fullname.startswith(('app.config','app.incident','app.queue','app.logging','app.time', 'app.ui', 'app.http_client', 'app.im.application', 'app.im.users')):
            raise AssertionError(fullname)
sys.meta_path.insert(0, NoPrivateCore())
from app.im.providers.slack import SlackProvider, TEMPLATE_NAMES
from app.im.providers.slack.authentication import SlackAuthentication
for name in TEMPLATE_NAMES:
    assert SlackProvider.template_source(name).strip()
"""
    result = subprocess.run(
        [sys.executable, '-c', script],
        cwd=tmp_path,
        env={**os.environ, 'PYTHONPATH': str(root) + os.pathsep + os.environ.get('PYTHONPATH', '')},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_slack_transitive_import_boundary_and_core_selection():
    import app.im.providers.slack as slack

    root = Path(slack.__file__).parent
    for path in root.rglob('*.py'):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                modules = [
                    resolve_name('.' * node.level + (node.module or ''), 'app.im.providers.slack')
                    if node.level
                    else node.module or ''
                ]
            elif isinstance(node, ast.Import):
                modules = [a.name for a in node.names]
            else:
                modules = []
            for module in modules:
                assert (
                    not module.startswith('app.')
                    or module == 'app.im.plugin_api'
                    or module.startswith('app.im.providers.slack')
                ), (path, module)
    for path in root.parents[2].rglob('*.py'):
        if 'providers' in path.parts or path.name == 'registry.py':
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or '').startswith('app.im.providers.slack'), path
            if isinstance(node, ast.Compare):
                assert not any(
                    (isinstance(n, ast.Constant) and n.value == 'slack')
                    or (isinstance(n, ast.Attribute) and n.attr == 'SLACK')
                    for n in ast.walk(node)
                ), path


@pytest.mark.asyncio
async def test_group_discovery_normalized_cache_admin_roles_and_task_button(runtime):
    app = get_application(
        config_for(
            'slack',
            users={'alice': {'id': 'U1'}},
            admin_users=['alice'],
            groups={'ops': {'id': 'G1'}, 'missing': {'id': 'G2'}},
        ),
        {'default': {'id': 'C1'}},
        'default',
    )
    transport = Transport()
    app._setup_http = Mock(return_value=transport)
    await app.initialize_async()
    assert app.users.get('alice').roles == ['admin']
    assert app.users.get('alice').get_notification_identifier() == 'U1'
    assert app.groups['ops'].exists and not app.groups['missing'].exists
    incident = incident_for('slack')
    message = replace(Application._presentation(incident, 'body', 'header', 'icon'), can_create_task=True)
    assert SlackProvider.payload(message)['attachments'][1]['actions'][-1]['name'] == 'task'
    assert all(r.closed for r in transport.responses)
    await app.close()


@pytest.mark.parametrize('provider_id', ['slack', 'mattermost', 'telegram', 'none'])
def test_config_roundtrip_preserves_provider_fields(provider_id):
    original = config_for(provider_id)
    config = ImpulseConfig(messenger=original, route={'channel': 'default'})
    values = config.model_dump()
    assert values['messenger'] == original.model_dump()
    assert ImpulseConfig.model_validate(values).messenger == original


@pytest.mark.asyncio
@pytest.mark.parametrize('timestamp,signature', [('9' * 1000, 'x'), ('invalid', 'x'), (str(int(time.time())), '☃')])
async def test_malformed_signature_headers_fail_closed(timestamp, signature):
    result = await make_provider(SLACK_SIGNING_SECRET='key').parse_interaction(
        request(callback(), (('x-slack-request-timestamp', timestamp), ('x-slack-signature', signature)))
    )
    assert result.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['fetch_user', 'fetch_groups'])
async def test_lookup_http_error_does_not_require_json(operation):
    provider = make_provider()
    response = Mock(status=503, json=AsyncMock(side_effect=ValueError('HTML response')))
    provider.http = Mock(get=AsyncMock(return_value=response))
    result = await (provider.fetch_user('U1') if operation == 'fetch_user' else provider.fetch_groups())
    assert (not result.exists) if operation == 'fetch_user' else result == ()
    response.json.assert_not_called()
    response.close.assert_called_once()


@pytest.mark.parametrize('key', ['body', 'header', 'status_icons'])
def test_all_template_override_keys_work_outside_checkout(key, tmp_path, monkeypatch, runtime):
    source = tmp_path / 'custom.j2'
    source.write_text('custom source')
    monkeypatch.chdir(tmp_path)
    app = get_application(config_for('slack', template_files={key: str(source)}), {'default': {'id': 'C1'}}, 'default')
    templates = app.generate_template()
    assert templates[['body', 'header', 'status_icons'].index(key)].form_message({}) == 'custom source'


@pytest.mark.asyncio
async def test_api_failure_log_never_includes_returned_secrets(caplog):
    provider = make_provider()
    response = Mock(status=200, json=AsyncMock(return_value={'ok': False, 'error': 'reflected-secret-value'}))
    provider.http = Mock(post=AsyncMock(return_value=response))
    assert (
        await provider.create_incident(Application._presentation(incident_for('slack'), 'body', 'header', 'icon'))
        is None
    )
    assert 'reflected-secret-value' not in caplog.text
    assert 'test-token' not in caplog.text
    response.close.assert_called_once()


@pytest.mark.asyncio
async def test_facade_requires_raw_request_instead_of_platform_dictionary(runtime):
    app = get_application(config_for('slack'), {'default': {'id': 'C1'}}, 'default')
    incidents = Mock()
    with pytest.raises(TypeError, match='InteractionRequest'):
        await app.buttons_handler(callback(), incidents, Mock(), Mock())
    incidents.get_by_ts.assert_not_called()


@pytest.mark.parametrize('invalid_id', [None, [], {}, 42])
def test_invalid_provider_ids_are_configuration_errors(invalid_id):
    with pytest.raises(ValidationError, match='provider ID'):
        ImpulseConfig.model_validate({'messenger': {'type': invalid_id}})


def test_blank_development_address_keeps_slack_default():
    assert make_provider(DEV_MESSENGER_CUSTOM_ADDRESS='  ').url == 'https://slack.com'
