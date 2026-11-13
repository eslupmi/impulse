"""Mattermost boundary checks exercise the registry facade and public provider DTOs."""

from dataclasses import replace
from unittest.mock import AsyncMock, Mock

import pytest

from app.im.application import Application
from app.im.helpers import get_application
from impulse_messenger_api import MessageRef, UserProfile
from impulse_mattermost import MattermostProvider
from tests.test_im.test_provider_seam import Response, config_for, incident_for, json_request, runtime  # noqa: F401


def make_provider(**secrets):
    return MattermostProvider(config_for('mattermost'), {'MATTERMOST_ACCESS_TOKEN': 'test-token', **secrets})


def test_closed_incident_update_payload_has_no_actions():
    message = replace(Application._presentation(incident_for('mattermost'), 'body', 'header', ':closed:'), status='closed')
    payload = make_provider().payload(message, update=True)
    assert payload['props']['attachments'][0]['text'] == 'body'
    assert 'actions' not in payload['props']['attachments'][0]


@pytest.mark.asyncio
async def test_buttons_handler_take_it_posts_assignment_notification(runtime):
    app = get_application(config_for('mattermost', users={'alice': {'id': 'U123'}}), {'default': {'id': 'C1'}}, 'default')
    app.fetch_and_assign_user_name = AsyncMock(
        side_effect=lambda incident, user_id, dump=True: setattr(incident, 'assigned_user_id', user_id) or True
    )
    app.post_assignment_notification = AsyncMock()
    app.form_body_header_status_icons = Mock(return_value=('body', 'header', ':firing:'))
    incident = incident_for('mattermost')
    incident.ts = 'post-1'
    result = await app.buttons_handler(
        json_request({'post_id': incident.ts, 'user_id': 'U123', 'context': {'action': 'chain'}}),
        Mock(get_by_ts=Mock(return_value=incident)),
        Mock(delete_by_id=AsyncMock()),
    )
    assert result.status_code == 200
    app.fetch_and_assign_user_name.assert_awaited_once_with(incident, 'U123', dump=False)
    assert incident.chain_enabled is False
    incident.dump.assert_called_once_with()
    import asyncio
    await asyncio.gather(*app._async_tasks)
    app.post_assignment_notification.assert_awaited_once_with(incident)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'status,body,expected',
    [
        (201, {'id': 'post_abc'}, MessageRef('C1', 'post_abc')),
        (401, {'id': 'api.context.session_expired.app_error', 'message': 'Invalid or expired session'}, None),
    ],
)
async def test_create_incident_response(status, body, expected):
    provider = make_provider()
    provider.callback_url = 'https://impulse.example.com/app'
    response = Response(body, status)
    provider.http = Mock(post=AsyncMock(return_value=response))
    result = await provider.create_incident(Application._presentation(incident_for('mattermost'), 'body', 'header', 'icon'))
    assert result == expected
    assert response.closed


def test_mention_uses_username():
    assert MattermostProvider.mention_id(UserProfile('abc123', True, username='bjohnson')) == 'bjohnson'
