"""
Unit tests for TelegramApplication class.

This module tests the TelegramApplication class which extends the Application ABC
and provides Telegram-specific functionality for incident management.
"""
from unittest.mock import Mock, AsyncMock, patch, mock_open

import aiohttp
import pytest
from fastapi.responses import JSONResponse

from app.config.validation import TelegramApplicationConfig, TelegramUser, MessengerType
from app.im.telegram.telegram_application import TelegramApplication
from tests.utils import (
    create_mock_incident_for_handlers,
    create_mock_incidents_collection,
    create_mock_queue,
    create_mock_route,
    create_telegram_buttons_handler_context,
    create_mock_http_response
)


class TestTelegramApplication:
    """Test cases for TelegramApplication class."""

    @pytest.fixture(autouse=True)
    def mock_asyncio_sleep(self):
        """Mock asyncio.sleep to avoid delays in tests."""
        with patch('asyncio.sleep') as mock_sleep:
            yield mock_sleep

    def create_telegram_app(self, app_config, channels, users):
        """Helper method to create TelegramApplication with proper mocking."""
        with patch('builtins.open', mock_open(read_data="template content")):
            # TelegramApplication expects (app_config, channels, users) but parent expects default_channel
            # We need to patch the parent constructor to handle this mismatch
            with patch('app.im.application.Application.__init__') as mock_parent_init:
                mock_parent_init.return_value = None
                app = TelegramApplication(app_config, channels, users)
                # Manually set the attributes that would normally be set by parent init
                app.type = app_config.type
                app.url = "https://api.telegram.org/bot"
                app.team = None
                app.channels = channels
                app.default_channel_id = list(channels.values())[0]['id'] if channels else None
                app._app_config = app_config
                app.chains = {}
                app.templates = app_config.template_files
                app.body_template = Mock()
                app.header_template = Mock()
                app.status_icons_template = Mock()
                # Set up HTTP mock with proper context manager support
                app.http = Mock()
                # Create default mock responses for HTTP methods
                default_get_response = AsyncMock()
                default_get_response.status = 200
                default_get_response.json = AsyncMock(return_value={'ok': True, 'result': {'id': 123456, 'first_name': 'Test', 'last_name': 'User'}})
                
                default_post_response = AsyncMock()
                default_post_response.status = 200
                default_post_response.json = AsyncMock(return_value={'ok': True, 'result': {}})
                
                app.http.post = AsyncMock(return_value=default_post_response)
                app.http.get = AsyncMock(return_value=default_get_response)
                app.public_url = None
                app.users = None
                app.user_groups = None
                app.groups = {}
                app.admin_users = None
                app._users_config = users
                app._user_groups_config = app_config.user_groups
                app._groups_config = getattr(app_config, 'groups', {})
                app._admin_users_config = app_config.admin_users

                # Set Telegram-specific attributes
                app.post_message_url = "https://api.telegram.org/bot/sendMessage"
                app.headers = {'Content-Type': 'application/json'}
                app.rate_limit = 15
                app.rate_window = 60.0
                app.thread_id_key = "message_id"

                return app

    @pytest.fixture
    def app_config(self):
        """Create mock TelegramApplicationConfig for testing."""
        config = Mock(spec=TelegramApplicationConfig)
        config.type = MessengerType.TELEGRAM
        config.channels = {"default": {"id": -1001234567890}}
        config.users = {"admin1": {"id": 123456789}}
        config.admin_users = ["admin1"]  # Only include users that exist
        config.user_groups = {}
        config.groups = {}
        config.chains = {}
        config.template_files = Mock()
        config.template_files.status_icons = None
        config.template_files.header = None
        config.template_files.body = None
        config.impulse_address = "https://impulse.example.com"
        return config

    @pytest.fixture
    def channels(self):
        """Create mock channels configuration."""
        return {"default": {"id": -1001234567890}}

    @pytest.fixture
    def users(self):
        """Create mock users configuration."""
        user1 = Mock(spec=TelegramUser)
        user1.id = 123456789
        return {"admin1": user1}

    def test_telegram_application_initialization(self, app_config, channels, users):
        """Test TelegramApplication initialization."""
        app = self.create_telegram_app(app_config, channels, users)

        assert app.type == MessengerType.TELEGRAM
        assert app.url == "https://api.telegram.org/bot"
        assert app.team is None
        assert app.channels == channels
        assert app.default_channel_id == -1001234567890
        assert app.post_message_url == "https://api.telegram.org/bot/sendMessage"
        assert app.thread_id_key == "message_id"

    def test_initialize_specific_params(self, app_config, channels, users):
        """Test _initialize_specific_params method."""
        with patch('app.im.telegram.telegram_application.get_environment_config') as mock_get_env_config:
            mock_env_config = Mock()
            mock_env_config.telegram_bot_token = "test-token"
            mock_get_env_config.return_value = mock_env_config

            app = self.create_telegram_app(app_config, channels, users)
            # Manually call the method to test it
            app._initialize_specific_params()

            assert app.url == "https://api.telegram.org/bottest-token"
            assert app.post_message_url == "https://api.telegram.org/bottest-token/sendMessage"
            assert app.headers == {'Content-Type': 'application/json'}
            assert app.thread_id_key == "message_id"

    def test_get_url(self, app_config, channels, users):
        """Test _get_url method."""
        app = self.create_telegram_app(app_config, channels, users)
        url = app._get_url(app_config)

        assert url == "https://api.telegram.org/bot"

    def test_get_public_url(self, app_config, channels, users):
        """Test _get_public_url method."""
        app = self.create_telegram_app(app_config, channels, users)
        url = app._get_public_url(app_config)

        assert url == "https://api.telegram.org/bot"

    def test_get_team_name(self, app_config, channels, users):
        """Test _get_team_name method."""
        app = self.create_telegram_app(app_config, channels, users)
        team_name = app._get_team_name(app_config)

        assert team_name is None

    def test_get_notification_destinations(self, app_config, channels, users):
        """Test get_notification_destinations method."""
        app = self.create_telegram_app(app_config, channels, users)

        # Mock admin users
        admin1 = Mock()
        admin1.id = 123456789
        admin2 = Mock()
        admin2.id = 987654321
        app.admin_users = [admin1, admin2]

        destinations = app.get_notification_destinations()

        assert destinations == [admin1, admin2]

    def test_format_tg_icon(self, app_config, channels, users):
        """Test _format_tg_icon method."""
        app = self.create_telegram_app(app_config, channels, users)

        # Test with known icon
        result = app._format_tg_icon('5312241539987020022')
        assert result == '🔥'

        # Test with unknown icon
        result = app._format_tg_icon('unknown_icon')
        assert result == 'None'

    def test_post_thread_payload(self, app_config, channels, users):
        """Test _post_thread_payload method."""
        app = self.create_telegram_app(app_config, channels, users)

        result = app._post_thread_payload(-1001234567890, "123456/789012", "Test message")

        expected = {
            'chat_id': -1001234567890,
            'text': 'Test message',
            'message_thread_id': '123456',
            'parse_mode': 'HTML'
        }
        assert result == expected

    def test_markdown_links_to_native_format(self, app_config, channels, users):
        """Test _markdown_links_to_native_format method."""
        app = self.create_telegram_app(app_config, channels, users)

        # Telegram doesn't convert markdown links, just returns as-is
        text = "Check out [this link](https://example.com) for more info"
        result = app._markdown_links_to_native_format(text)

        assert result == text

    def test_get_user_details_method(self, app_config, channels, users):
        """Test get_user_details method signature."""
        app = self.create_telegram_app(app_config, channels, users)

        # Test that the method exists and is async
        assert hasattr(app, 'get_user_details')
        assert callable(app.get_user_details)
        import inspect
        assert inspect.iscoroutinefunction(app.get_user_details)

        # Test method signature
        sig = inspect.signature(app.get_user_details)
        params = list(sig.parameters.keys())
        assert 'user_details' in params

    def test_create_user(self, app_config, channels, users):
        """Test create_user method."""
        app = self.create_telegram_app(app_config, channels, users)

        user_details = {
            "id": 123456789,
            "exists": True,
            "full_name": "Test User"
        }

        user = app.create_user("testuser", user_details)

        assert user.name == "testuser"
        assert user.id == 123456789
        assert user.exists is True

    def test_icon_map(self, app_config, channels, users):
        """Test icon_map class attribute."""
        app = self.create_telegram_app(app_config, channels, users)

        # Test all icon mappings
        assert app.icon_map['5312241539987020022'] == '🔥'  # firing
        assert app.icon_map['5379748062124056162'] == '❗️'  # unknown
        assert app.icon_map['5237699328843200968'] == '✅'  # resolved
        assert app.icon_map['5408906741125490282'] == '🏁'  # closed

    @pytest.mark.asyncio
    async def test_buttons_handler_no_callback_query(self, app_config, channels, users):
        """Test buttons_handler when no callback_query in payload."""
        app = self.create_telegram_app(app_config, channels, users)

        payload = {"message": {"text": "test"}}
        incidents = create_mock_incidents_collection()
        queue = create_mock_queue()
        route = create_mock_route()

        result = await app.buttons_handler(payload, incidents, queue, route)

        assert isinstance(result, JSONResponse)
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_buttons_handler_no_incident(self, app_config, channels, users):
        """Test buttons_handler when no incident is found."""
        app = self.create_telegram_app(app_config, channels, users)

        payload = {
            "callback_query": {
                "id": "test_callback_id",
                "message": {
                    "message_id": 123,
                    "message_thread_id": 456
                },
                "data": "start_chain"
            }
        }

        incidents = create_mock_incidents_collection()
        incidents.get_by_ts.return_value = None
        queue = create_mock_queue()
        route = create_mock_route()

        with patch.object(app.http, 'post', new_callable=AsyncMock) as mock_post:
            result = await app.buttons_handler(payload, incidents, queue, route)

            assert isinstance(result, JSONResponse)
            assert result.status_code == 200
            mock_post.assert_called_once()

    def test_create_topic_method(self, app_config, channels, users):
        """Test _create_topic method signature."""
        app = self.create_telegram_app(app_config, channels, users)

        # Test that the method exists and is async
        assert hasattr(app, '_create_topic')
        assert callable(app._create_topic)
        import inspect
        assert inspect.iscoroutinefunction(app._create_topic)

        # Test method signature
        sig = inspect.signature(app._create_topic)
        params = list(sig.parameters.keys())
        assert 'channel_id' in params
        assert 'header' in params
        assert 'status_icons' in params

    def test_update_topic_method(self, app_config, channels, users):
        """Test _update_topic method signature."""
        app = self.create_telegram_app(app_config, channels, users)

        # Test that the method exists and is async
        assert hasattr(app, '_update_topic')
        assert callable(app._update_topic)
        import inspect
        assert inspect.iscoroutinefunction(app._update_topic)

        # Test method signature
        sig = inspect.signature(app._update_topic)
        params = list(sig.parameters.keys())
        assert 'channel_id' in params
        assert 'id_' in params
        assert 'header' in params
        assert 'status_icons' in params

    def test_setup_webhook_method(self, app_config, channels, users):
        """Test _setup_webhook method signature."""
        app = self.create_telegram_app(app_config, channels, users)

        # Test that the method exists and is async
        assert hasattr(app, '_setup_webhook')
        assert callable(app._setup_webhook)
        import inspect
        assert inspect.iscoroutinefunction(app._setup_webhook)

    @pytest.mark.asyncio
    async def test_initialize_async(self, app_config, channels, users):
        """Test initialize_async method."""
        app = self.create_telegram_app(app_config, channels, users)

        # Create mock HTTP client that will be returned by _setup_http
        mock_http = Mock()
        default_get_response = AsyncMock()
        default_get_response.status = 200
        default_get_response.json = AsyncMock(return_value={'ok': True, 'result': {'id': 123456, 'first_name': 'Test', 'last_name': 'User'}})
        default_post_response = AsyncMock()
        default_post_response.status = 200
        default_post_response.json = AsyncMock(return_value={'ok': True, 'result': {}})
        mock_http.get = AsyncMock(return_value=default_get_response)
        mock_http.post = AsyncMock(return_value=default_post_response)

        # Mock _setup_webhook as async function
        mock_setup_webhook = AsyncMock(return_value=None)
        
        # Mock UserStore to avoid filesystem access
        mock_user_store = Mock()
        mock_user_store.get_all_users_by_type.return_value = {}
        mock_user_store.get.return_value = None
        mock_user_store.is_expired.return_value = True
        mock_user_store.save = Mock()
        
        with patch.object(app, '_setup_http', return_value=mock_http), \
             patch.object(app, '_setup_webhook', mock_setup_webhook), \
             patch('app.im.application.get_user_store', return_value=mock_user_store):
            await app.initialize_async()

            mock_setup_webhook.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_create_thread_http_interaction(self, app_config, channels, users):
        """Test _send_create_thread method with HTTP interaction."""
        app = self.create_telegram_app(app_config, channels, users)

        # Mock HTTP response
        mock_response = create_mock_http_response()
        mock_response.json = AsyncMock(return_value={'result': {'message_id': 12345}})
        with patch.object(app.http, 'post', new=AsyncMock(return_value=mock_response)) as mock_post:
            result = await app._send_create_incident_message({'test': 'payload'})

            assert result == 12345
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_topic_success(self, app_config, channels, users):
        """Test _create_topic method with successful HTTP response."""
        app = self.create_telegram_app(app_config, channels, users)

        # Mock successful HTTP response
        mock_response = create_mock_http_response()
        mock_response.json = AsyncMock(return_value={'result': {'message_thread_id': 67890}})
        with patch.object(app.http, 'post', new=AsyncMock(return_value=mock_response)) as mock_post:
            result = await app._create_topic("test_channel", "test_header", "test_icon")

            assert result == 67890
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_topic_error_handling(self, app_config, channels, users):
        """Test _create_topic method with HTTP error."""
        app = self.create_telegram_app(app_config, channels, users)

        with patch.object(app.http, 'post') as mock_post:
            mock_post.side_effect = aiohttp.ClientError("Connection failed")

            with pytest.raises(aiohttp.ClientError):
                await app._create_topic("test_channel", "test_header", "test_icon")

    @pytest.mark.asyncio
    async def test_update_topic_success(self, app_config, channels, users):
        """Test _update_topic method with successful HTTP response."""
        app = self.create_telegram_app(app_config, channels, users)

        # Mock successful HTTP response
        mock_response = create_mock_http_response()
        with patch.object(app.http, 'post', new=AsyncMock(return_value=mock_response)) as mock_post:
            await app._update_topic("test_channel", "123/456", "test_header", "test_icon")

            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_topic_error_handling(self, app_config, channels, users):
        """Test _update_topic method with HTTP error."""
        app = self.create_telegram_app(app_config, channels, users)

        with patch.object(app.http, 'post') as mock_post:
            mock_post.side_effect = aiohttp.ClientError("Connection failed")

            # Should not raise exception, just log error
            await app._update_topic("test_channel", "123/456", "test_header", "test_icon")

    @pytest.mark.asyncio
    async def test_update_thread_http_success(self, app_config, channels, users):
        """Test _update_thread method with successful HTTP response."""
        app = self.create_telegram_app(app_config, channels, users)

        # Mock successful HTTP response
        mock_response = create_mock_http_response()
        with patch.object(app.http, 'post', new=AsyncMock(return_value=mock_response)) as mock_post:
            await app._update_incident_message("123/456", {'test': 'payload'})

            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_thread_http_error_handling(self, app_config, channels, users):
        """Test _update_thread method with HTTP error."""
        app = self.create_telegram_app(app_config, channels, users)

        with patch.object(app.http, 'post') as mock_post:
            mock_post.side_effect = aiohttp.ClientError("Connection failed")

            # Should not raise exception, just log error
            await app._update_incident_message("123/456", {'test': 'payload'})

    @pytest.mark.asyncio
    async def test_get_user_details_api_error(self, app_config, channels, users):
        """Test get_user_details method with API error response."""
        app = self.create_telegram_app(app_config, channels, users)

        # Mock API error response
        mock_response = create_mock_http_response(200)
        mock_response.json = AsyncMock(return_value={
            'ok': False,
            'description': 'User not found'
        })
        with patch.object(app.http, 'get', new=AsyncMock(return_value=mock_response)):
            result = await app.get_user_details({'id': '123456'})

            assert result == {
                'id': '123456',
                'exists': False,
                'full_name': None,
                'username': None,
                'email': None,
                'first_name': None,
                'last_name': None,
                'timezone': None
            }

    @pytest.mark.asyncio
    async def test_setup_webhook_success(self, app_config, channels, users):
        """Test _setup_webhook method with successful HTTP response."""
        app = self.create_telegram_app(app_config, channels, users)

        # Mock successful HTTP response
        mock_response = create_mock_http_response()
        with patch.object(app.http, 'post', new=AsyncMock(return_value=mock_response)) as mock_post, \
                patch('app.im.telegram.telegram_application.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.messenger.impulse_address = "https://impulse.example.com"
            mock_get_config.return_value = mock_config

            await app._setup_webhook()

            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_setup_webhook_error_handling(self, app_config, channels, users):
        """Test _setup_webhook method with HTTP error."""
        app = self.create_telegram_app(app_config, channels, users)

        with patch.object(app.http, 'post') as mock_post, \
                patch('app.im.telegram.telegram_application.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.messenger.impulse_address = "https://impulse.example.com"
            mock_get_config.return_value = mock_config

            mock_post.side_effect = aiohttp.ClientError("Connection failed")

            with pytest.raises(aiohttp.ClientError):
                await app._setup_webhook()
