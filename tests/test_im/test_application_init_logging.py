import asyncio
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest

from app.config.validation import MessengerType, SlackApplicationConfig, SlackUser
from app.im.slack.slack_application import SlackApplication


class TestApplicationInitLogging:
    @pytest.fixture
    def slack_app(self):
        config = Mock(spec=SlackApplicationConfig)
        config.type = MessengerType.SLACK
        config.template_files = {}
        config.chains = {}
        config.users = {'alice': Mock(spec=SlackUser, id='U1')}
        config.user_groups = {}
        config.groups = {}
        config.admin_users = []
        config.address = 'https://slack.example.com'

        channels = {'default': {'id': 'C1'}}

        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__ = Mock(return_value=Mock(read=Mock(return_value='')))
            mock_open.return_value.__exit__ = Mock(return_value=False)
            with patch('app.im.application.ChainFactory.generate', return_value={}):
                app = SlackApplication(config, channels, 'default')

        return app

    @pytest.mark.asyncio
    async def test_initialize_async_logs_step_for_non_transport_failure(self, slack_app):
        mock_http = Mock()
        auth_response = AsyncMock()
        auth_response.json = AsyncMock(return_value={'url': 'https://slack.example.com'})
        auth_response.close = Mock()
        mock_http.get = AsyncMock(return_value=auth_response)

        with patch.object(slack_app, '_setup_http', return_value=mock_http), \
                patch.object(slack_app, '_generate_users', new=AsyncMock(side_effect=ValueError('bad users config'))), \
                patch('app.im.messenger_init.logger') as mock_logger:
            with pytest.raises(ValueError, match='bad users config'):
                await slack_app.initialize_async()

            mock_logger.error.assert_called_once()
            extra = mock_logger.error.call_args[1]['extra']
            assert extra['step'] == 'users'
            assert extra['messenger'] == 'slack'
            assert extra['error_type'] == 'ValueError'
            assert extra['detail'] == 'bad users config'

    @pytest.mark.asyncio
    async def test_initialize_async_skips_step_log_for_transport_failure(self, slack_app):
        mock_http = Mock()
        auth_response = AsyncMock()
        auth_response.json = AsyncMock(return_value={'url': 'https://slack.example.com'})
        auth_response.close = Mock()
        mock_http.get = AsyncMock(return_value=auth_response)

        with patch.object(slack_app, '_setup_http', return_value=mock_http), \
                patch.object(
                    slack_app,
                    '_generate_users',
                    new=AsyncMock(side_effect=aiohttp.ClientConnectionError('connection failed')),
                ), \
                patch('app.im.messenger_init.logger') as mock_logger:
            with pytest.raises(aiohttp.ClientConnectionError):
                await slack_app.initialize_async()

            mock_logger.error.assert_not_called()

    @pytest.mark.asyncio
    async def test_initialize_async_transport_failure_includes_step_in_http_log(self, slack_app):
        from app.http_client import RateLimitedClient

        http_client = RateLimitedClient(retry_attempts=1)
        http_client.initialize_client()

        with patch.object(slack_app, '_setup_http', return_value=http_client), \
                patch.object(
                    http_client._client,
                    'request',
                    new=AsyncMock(side_effect=aiohttp.ClientConnectionError('connection failed')),
                ), \
                patch('app.http_client.rate_limited_client.logger') as mock_logger, \
                patch('app.im.messenger_init.logger') as mock_init_logger:
            with pytest.raises(aiohttp.ClientConnectionError):
                await slack_app.initialize_async()

            mock_init_logger.error.assert_not_called()
            extra = mock_logger.error.call_args[1]['extra']
            assert extra['step'] == 'public_url'
            assert extra['messenger'] == 'slack'
            assert extra['failure'] == 'connection_failed'


class TestMeasureRequestMetrics:
    @pytest.mark.asyncio
    async def test_connection_error_is_labeled_connection_failed(self):
        from app.metrics import API_LATENCY, measure_request

        class Client:
            @measure_request
            async def request(self):
                raise aiohttp.ClientConnectionError('connection failed')

        mock_labels = Mock()
        with patch.object(API_LATENCY, 'labels', return_value=mock_labels) as mock_label_factory:
            with pytest.raises(aiohttp.ClientConnectionError):
                await Client().request()

            mock_label_factory.assert_called_once_with(status='no_response', error='connection_failed')
            mock_labels.observe.assert_called_once()
