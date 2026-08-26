import asyncio

import aiohttp

from app.http_client.errors import MESSENGER_TRANSPORT_ERRORS, classify_messenger_http_error


class TestClassifyMessengerHttpError:
    def test_timeout(self):
        assert classify_messenger_http_error(asyncio.TimeoutError()) == 'timeout'
        assert classify_messenger_http_error(aiohttp.ServerTimeoutError()) == 'timeout'

    def test_connection_failed(self):
        assert classify_messenger_http_error(aiohttp.ClientConnectionError('connection failed')) == 'connection_failed'

    def test_unknown(self):
        assert classify_messenger_http_error(aiohttp.ClientError()) == 'unknown'
        assert classify_messenger_http_error(ValueError('bad config')) == 'unknown'

    def test_messenger_transport_errors_tuple(self):
        assert isinstance(asyncio.TimeoutError(), MESSENGER_TRANSPORT_ERRORS)
        assert isinstance(aiohttp.ClientConnectionError('x'), MESSENGER_TRANSPORT_ERRORS)
