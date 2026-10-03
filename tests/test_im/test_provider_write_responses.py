"""Rejected writes must surface safely and release their HTTP responses."""
import traceback
from unittest.mock import AsyncMock, Mock

import pytest

from impulse_mattermost import MattermostProvider
from impulse_slack import SlackProvider
from impulse_telegram import TelegramProvider
from tests.test_im.test_provider_seam import Response, config_for
from tests.test_im.test_telegram.test_telegram_application import presentation, request

TOKEN = 'reflected-write-secret'


def write_provider(provider_id, responses):
    factory = {'slack': SlackProvider, 'mattermost': MattermostProvider, 'telegram': TelegramProvider}[provider_id]
    provider = factory(config_for(provider_id), {
        'SLACK_BOT_USER_OAUTH_TOKEN': TOKEN, 'SLACK_VERIFICATION_TOKEN': 'verify',
        'MATTERMOST_ACCESS_TOKEN': TOKEN, 'TELEGRAM_BOT_TOKEN': TOKEN,
    })
    provider.http = Mock(post=AsyncMock(side_effect=responses), put=AsyncMock(side_effect=responses))
    return provider


async def write(provider, operation):
    if operation == 'activate':
        await provider.activate()
    elif operation == 'after_interaction':
        await provider.after_interaction(presentation(), await provider.parse_interaction(request('freeze_menu')))
    else:
        await getattr(provider, operation)(presentation())


@pytest.mark.asyncio
@pytest.mark.parametrize('provider_id, operation, status, body', [
    ('slack', 'update_incident', 200, {'ok': False, 'error': TOKEN}),
    ('slack', 'update_incident', 503, {'error': TOKEN}),
    ('slack', 'update_incident', 200, []),
    ('mattermost', 'update_incident', 401, {'message': TOKEN}),
    ('telegram', 'activate', 200, {'ok': False, 'description': TOKEN}),
    ('telegram', 'activate', 400, {'ok': False, 'description': TOKEN}),
    ('telegram', 'activate', 200, []),
    ('telegram', 'update_incident', 403, {'ok': False, 'description': TOKEN}),
    ('telegram', '_edit_message', 200, {'ok': False, 'description': TOKEN}),
    ('telegram', 'after_interaction', 400, {'ok': False, 'description': TOKEN}),
])
async def test_rejected_write_raises_redacted_error_and_closes_response(provider_id, operation, status, body):
    response = Response(body, status)
    provider = write_provider(provider_id, [response])
    with pytest.raises(RuntimeError, match=f'HTTP {status}') as error:
        await write(provider, operation)
    assert TOKEN not in ''.join(traceback.format_exception(type(error.value), error.value, error.value.__traceback__))
    assert response.closed
    assert provider.http.post.await_count + provider.http.put.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('provider_id, operation', [
    ('slack', 'update_incident'),
    ('telegram', 'activate'),
    ('telegram', 'update_incident'),
    ('telegram', '_edit_message'),
    ('telegram', 'after_interaction'),
])
async def test_invalid_write_json_is_redacted_and_response_closed(provider_id, operation):
    response = Response({})
    response.json = AsyncMock(side_effect=ValueError(f'invalid JSON from https://api.test/bot{TOKEN}'))
    provider = write_provider(provider_id, [response])
    with pytest.raises(RuntimeError, match='invalid response') as error:
        await write(provider, operation)
    assert TOKEN not in ''.join(traceback.format_exception(type(error.value), error.value, error.value.__traceback__))
    assert response.closed


@pytest.mark.asyncio
@pytest.mark.parametrize('provider_id, status, body', [
    ('slack', 200, {'ok': True}),
    ('mattermost', 200, {'id': 'post-1'}),
    ('mattermost', 204, None),
])
async def test_successful_update_closes_response(provider_id, status, body):
    response = Response(body, status)
    provider = write_provider(provider_id, [response])
    await provider.update_incident(presentation())
    assert response.closed


@pytest.mark.asyncio
async def test_telegram_unchanged_topic_still_updates_message_and_accepts_unchanged_text():
    topic = Response({'ok': False, 'error_code': 400, 'description': 'Bad Request: TOPIC_NOT_MODIFIED'}, 400)
    message = Response({'ok': False, 'error_code': 400, 'description':
        'Bad Request: message is not modified: specified new message content and reply markup are exactly '
        'the same as a current content and reply markup of the message'}, 400)
    provider = write_provider('telegram', [topic, message])
    await provider.update_incident(presentation())
    assert provider.http.post.await_count == 2
    assert provider.http.post.await_args_list[-1].args[0].endswith('/editMessageText')
    assert topic.closed and message.closed


@pytest.mark.asyncio
async def test_telegram_unchanged_callback_edit_still_acknowledges_callback():
    unchanged = Response({'ok': False, 'error_code': 400, 'description': 'Bad Request: message is not modified'}, 400)
    acknowledged = Response({'ok': True, 'result': True})
    provider = write_provider('telegram', [unchanged, acknowledged])
    await write(provider, 'after_interaction')
    assert provider.http.post.await_args_list[-1].args[0].endswith('/answerCallbackQuery')
    assert unchanged.closed and acknowledged.closed


@pytest.mark.asyncio
@pytest.mark.parametrize('status, operation, error_code, description', [
    (200, '_edit_message', 400, 'Bad Request: message is not modified'),
    (500, '_edit_message', 400, 'Bad Request: message is not modified'),
    (400, '_edit_message', 403, 'Bad Request: message is not modified'),
    (400, 'activate', 400, 'Bad Request: message is not modified'),
    (400, 'update_incident', 400, 'Bad Request: message is not modified'),
    (400, '_edit_message', 400, 'Bad Request: TOPIC_NOT_MODIFIED'),
    (400, '_edit_message', 400, 'Bad Request: message is not modified but permission was denied'),
])
async def test_telegram_unchanged_error_is_only_accepted_for_matching_edit(status, operation, error_code, description):
    response = Response({'ok': False, 'error_code': error_code, 'description': description}, status)
    provider = write_provider('telegram', [response])
    with pytest.raises(RuntimeError):
        await write(provider, operation)
    assert response.closed
