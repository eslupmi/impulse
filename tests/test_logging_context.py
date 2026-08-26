import asyncio
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from app.http_client.rate_limited_client import RateLimitedClient
from app.logging_context import (
    MessengerInitContext,
    exception_fields,
    messenger_init_context,
    redact_messenger_url,
    transport_failure_fields,
)


class TestRedactMessengerUrl:
    def test_redacts_telegram_bot_token(self):
        url = 'https://api.telegram.org/bot123456:ABC-DEF/getChat'
        assert redact_messenger_url(url) == 'https://api.telegram.org/bot***/getChat'

    def test_redacts_telegram_base_url_with_token(self):
        url = 'https://api.telegram.org/bot123456:ABC-DEF'
        assert redact_messenger_url(url) == 'https://api.telegram.org/bot***'

    def test_leaves_non_telegram_urls_unchanged(self):
        url = 'https://mattermost.example.com/api/v4/users'
        assert redact_messenger_url(url) == url


class TestExceptionFields:
    def test_includes_error_type_and_detail(self):
        assert exception_fields(ValueError('bad config')) == {
            'error_type': 'ValueError',
            'detail': 'bad config',
        }

    def test_uses_error_type_when_detail_is_empty(self):
        assert exception_fields(asyncio.TimeoutError()) == {
            'error_type': 'TimeoutError',
            'detail': 'TimeoutError',
        }


class TestTransportFailureFields:
    def test_classifies_timeout(self):
        assert transport_failure_fields(asyncio.TimeoutError()) == {
            'failure': 'timeout',
            'detail': 'timeout',
        }

    def test_classifies_connection_failed(self):
        assert transport_failure_fields(aiohttp.ClientConnectionError('connection failed')) == {
            'failure': 'connection_failed',
            'detail': 'connection failed',
        }


class TestMessengerInitContext:
    @pytest.mark.asyncio
    async def test_transport_log_includes_init_step(self):
        token = messenger_init_context.set(MessengerInitContext(step='users', messenger='slack'))

        try:
            with patch('app.http_client.rate_limited_client.logger') as mock_logger:
                async with RateLimitedClient(retry_attempts=1) as client:
                    client.initialize_client()
                    with patch.object(
                        client._client,
                        'request',
                        new=AsyncMock(side_effect=aiohttp.ClientConnectionError('connection failed')),
                    ):
                        with pytest.raises(aiohttp.ClientConnectionError):
                            await client.get('https://slack.example.com/api/users.info')

                extra = mock_logger.error.call_args[1]['extra']
                assert extra['step'] == 'users'
                assert extra['messenger'] == 'slack'
                assert extra['failure'] == 'connection_failed'
        finally:
            messenger_init_context.reset(token)
