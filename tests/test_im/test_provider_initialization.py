"""Startup ordering and response handling through the provider boundary."""

from unittest.mock import AsyncMock, Mock

import pytest

from app.im.application import Application
from app.im.helpers import get_application
from tests.test_im.test_provider_seam import Response, Transport, config_for, incident_for, runtime  # noqa: F401

pytestmark = pytest.mark.usefixtures('runtime')


@pytest.mark.asyncio
@pytest.mark.parametrize('provider_id', ['slack', 'mattermost', 'telegram'])
async def test_activation_follows_core_state_loading_and_precedes_success_log(provider_id, monkeypatch):
    user_id = 123 if provider_id == 'telegram' else 'U1'
    config = config_for(provider_id, users={'alice': {'id': user_id}}, admin_users=['alice'])
    app = get_application(config, {'default': {'id': config.channels['default'].id}}, 'default')
    transport = Transport()
    app._setup_http = Mock(return_value=transport)
    activate = app.provider.activate
    events = []

    async def activate_with_loaded_state():
        assert app.users.get('alice').exists
        assert app.admin_users == [app.users.get('alice')]
        assert app.user_groups == {}
        assert app.groups == {}
        events.append('activate')
        await activate()

    def log(message, **kwargs):
        if message == 'Messenger initialized':
            events.append('initialized')

    monkeypatch.setattr(app.provider, 'activate', activate_with_loaded_state)
    monkeypatch.setattr('app.im.application.logger.info', log)
    await app.initialize_async()
    assert events == ['activate', 'initialized']
    if provider_id == 'telegram':
        urls = [url for _, url, _ in transport.calls]
        assert '/getChat?' in urls[0]
        assert urls[-1].endswith('/setWebhook')
        assert transport.calls[-1][2]['params'] == {'url': 'http://impulse.test/app'}
    assert all(response.closed for response in transport.responses)
    await app.close()


@pytest.mark.asyncio
async def test_failed_activation_does_not_log_success(monkeypatch):
    app = get_application(config_for('telegram'), {'default': {'id': -100123}}, 'default')
    app._setup_http = Mock(return_value=Transport())
    app.provider.activate = AsyncMock(side_effect=ValueError('activation failed'))
    logger = Mock()
    monkeypatch.setattr('app.im.application.logger', logger)
    with pytest.raises(ValueError, match='activation failed'):
        await app.initialize_async()
    assert all(call.args[0] != 'Messenger initialized' for call in logger.info.call_args_list)
    await app.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('provider_id, lookup', [
    ('slack', 'user'), ('slack', 'groups'), ('mattermost', 'user'), ('mattermost', 'groups'), ('telegram', 'user'),
])
async def test_failed_lookups_skip_non_json_bodies_and_close_responses(provider_id, lookup):
    config = config_for(provider_id, **({'groups': {'group': {'id': 'G1'}}} if provider_id == 'mattermost' else {}))
    provider = get_application(config, {'default': {'id': 'C1'}}, 'default').provider
    response = Response({}, status=500)
    response.json = AsyncMock(side_effect=ValueError('non-JSON error body'))
    provider.http = Mock(get=AsyncMock(return_value=response))
    if lookup == 'user':
        assert not (await provider.fetch_user(123 if provider_id == 'telegram' else 'U1')).exists
    else:
        groups = await provider.fetch_groups()
        assert all(not group.exists for group in groups)
    response.json.assert_not_awaited()
    assert response.closed


@pytest.mark.asyncio
@pytest.mark.parametrize('provider_id', ['slack', 'mattermost', 'telegram'])
async def test_incident_json_failure_propagates_and_closes_response(provider_id):
    provider = get_application(config_for(provider_id), {'default': {'id': 'C1'}}, 'default').provider
    response = Response({})
    response.json = AsyncMock(side_effect=ValueError('invalid JSON'))
    provider.http = Mock(post=AsyncMock(return_value=response))
    message = Application._presentation(incident_for(provider_id), 'body', 'header', 'icon')
    with pytest.raises(ValueError, match='invalid JSON'):
        await provider.create_incident(message)
    assert response.closed
