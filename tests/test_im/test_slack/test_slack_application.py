"""Slack boundary checks exercise the registry facade and public provider DTOs."""

from dataclasses import replace
from unittest.mock import AsyncMock, Mock

import pytest
from app.im.helpers import get_application
from impulse_messenger_api import MessageRef
from impulse_slack import SlackProvider
from tests.test_im.test_provider_seam import config_for, incident_for, Response, runtime, interaction_request  # noqa: F401
from app.im.application import Application


def make_provider(**secrets):
    return SlackProvider(
        config_for('slack'),
        {'SLACK_BOT_USER_OAUTH_TOKEN': 'test-token', 'SLACK_VERIFICATION_TOKEN': 'verify', **secrets},
    )


def test_closed_incident_update_payload_has_no_actions():
    message = Application._presentation(incident_for('slack'), 'body', 'header', ':closed:')
    payload = SlackProvider.payload(replace(message, status='closed'), update=True)
    assert len(payload['attachments']) == 1
    assert payload['attachments'][0]['text'] == 'body'


@pytest.mark.asyncio
async def test_buttons_handler_take_it_posts_assignment_notification(runtime):
    app = get_application(config_for('slack'), {'default': {'id': 'C1'}}, 'default')
    app.fetch_and_assign_user_name = AsyncMock(
        side_effect=lambda incident, user_id, dump=True: setattr(incident, 'assigned_user_id', user_id)
    )
    app.post_assignment_notification = AsyncMock()
    app.form_body_header_status_icons = Mock(return_value=('body', 'header', ':firing:'))
    incident = incident_for('slack')
    incident.ts = '123.456'
    result = await app.buttons_handler(
        interaction_request({
            'token': 'verify',
            'message_ts': incident.ts,
            'user': {'id': 'U123'},
            'actions': [{'name': 'chain'}],
            'original_message': {'text': 'original'},
        }),
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
        (200, {'ok': True, 'ts': '1700000000.000100'}, MessageRef('C1', '1700000000.000100')),
        (200, {'ok': False, 'error': 'channel_not_found'}, None),
        (500, {'error': 'server_error'}, None),
    ],
)
async def test_create_incident_response(status, body, expected):
    provider = make_provider()
    response = Response(body, status)
    provider.http = Mock(post=AsyncMock(return_value=response))
    result = await provider.create_incident(Application._presentation(incident_for('slack'), 'body', 'header', 'icon'))
    assert result == expected
    assert response.closed


@pytest.mark.parametrize(
    'override,expected', [(None, 'https://slack.com'), ('http://mock-slack:8080/', 'http://mock-slack:8080')]
)
def test_api_address(override, expected):
    assert make_provider(DEV_MESSENGER_CUSTOM_ADDRESS=override).url == expected
