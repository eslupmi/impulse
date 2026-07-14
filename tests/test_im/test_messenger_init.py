import asyncio
from unittest.mock import Mock, patch

import aiohttp
import pytest

from app.im.messenger_init import messenger_init_step_async, messenger_init_step_sync


class StubApplication:
    type = Mock(value='telegram')
    url = 'https://api.telegram.org/botsecret-token'


class TestMessengerInitStep:
    @pytest.mark.asyncio
    async def test_async_step_logs_and_reraises_non_transport_errors(self):
        app = StubApplication()

        @messenger_init_step_async('users')
        async def init_users(self):
            raise ValueError('invalid user config')

        with patch('app.im.messenger_init.logger') as mock_logger:
            with pytest.raises(ValueError, match='invalid user config'):
                await init_users(app)

            mock_logger.error.assert_called_once()
            extra = mock_logger.error.call_args[1]['extra']
            assert extra['step'] == 'users'
            assert extra['url'] == 'https://api.telegram.org/bot***'
            assert extra['error_type'] == 'ValueError'
            assert extra['detail'] == 'invalid user config'

    @pytest.mark.asyncio
    async def test_async_step_skips_logging_for_transport_errors(self):
        app = StubApplication()

        @messenger_init_step_async('users')
        async def init_users(self):
            raise aiohttp.ClientConnectionError('connection failed')

        with patch('app.im.messenger_init.logger') as mock_logger:
            with pytest.raises(aiohttp.ClientConnectionError):
                await init_users(app)

            mock_logger.error.assert_not_called()

    def test_sync_step_logs_and_reraises_non_transport_errors(self):
        app = StubApplication()

        @messenger_init_step_sync('http_client')
        def init_http(self):
            raise RuntimeError('setup failed')

        with patch('app.im.messenger_init.logger') as mock_logger:
            with pytest.raises(RuntimeError, match='setup failed'):
                init_http(app)

            mock_logger.error.assert_called_once()
            extra = mock_logger.error.call_args[1]['extra']
            assert extra['step'] == 'http_client'
            assert extra['error_type'] == 'RuntimeError'
            assert extra['detail'] == 'setup failed'

    def test_sync_step_skips_logging_for_transport_errors(self):
        app = StubApplication()

        @messenger_init_step_sync('http_client')
        def init_http(self):
            raise asyncio.TimeoutError()

        with patch('app.im.messenger_init.logger') as mock_logger:
            with pytest.raises(asyncio.TimeoutError):
                init_http(app)

            mock_logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_step_returns_value(self):
        app = StubApplication()

        @messenger_init_step_async('groups')
        async def init_groups(self):
            return {'oncall': 'team-a'}

        result = await init_groups(app)
        assert result == {'oncall': 'team-a'}

    def test_sync_step_returns_value(self):
        app = StubApplication()

        @messenger_init_step_sync('user_groups')
        def init_user_groups(self):
            return {}

        assert init_user_groups(app) == {}
