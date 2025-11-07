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
    create_telegram_buttons_handler_context
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
                app.http.post = Mock()
                app.http.get = Mock()
                app.public_url = None
                app.users = None
                app.user_groups = None
                app.admin_users = None
                app._users_config = users
                app._user_groups_config = app_config.user_groups
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
        with patch('app.im.telegram.telegram_application.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.telegram_bot_token = "test-token"
            mock_get_config.return_value = mock_config

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

    def test_get_admins_text(self, app_config, channels, users):
        """Test get_admins_text method."""
        app = self.create_telegram_app(app_config, channels, users)

        # Mock admin users
        admin1 = Mock()
        admin1.id = 123456789
        admin2 = Mock()
        admin2.id = 987654321
        app.admin_users = [admin1, admin2]

        result = app.get_admins_text()

        assert result == "@123456789, @987654321"

    def test_send_message_method(self, app_config, channels, users):
        """Test send_message method signature."""
        app = self.create_telegram_app(app_config, channels, users)

        # Test that the method exists and is async
        assert hasattr(app, 'send_message')
        assert callable(app.send_message)
        import inspect
        assert inspect.iscoroutinefunction(app.send_message)

        # Test method signature
        sig = inspect.signature(app.send_message)
        params = list(sig.parameters.keys())
        assert 'channel_id' in params
        assert 'text' in params
        assert 'attachment' in params

    def test_create_thread_method(self, app_config, channels, users):
        """Test create_thread method signature."""
        app = self.create_telegram_app(app_config, channels, users)

        # Test that the method exists and is async
        assert hasattr(app, 'create_thread')
        assert callable(app.create_thread)
        import inspect
        assert inspect.iscoroutinefunction(app.create_thread)

        # Test method signature
        sig = inspect.signature(app.create_thread)
        params = list(sig.parameters.keys())
        assert 'channel_id' in params
        assert 'body' in params
        assert 'header' in params
        assert 'status_icons' in params
        assert 'status' in params

    def test_create_thread_payload(self, app_config, channels, users):
        """Test _create_thread_payload method."""
        app = self.create_telegram_app(app_config, channels, users)

        with patch('app.im.telegram.telegram_application.buttons') as mock_buttons:
            mock_buttons.__getitem__.return_value = {
                'takeit': {'text': 'Take It', 'callback_data': 'start_chain'},
                'enabled': {'text': 'Status', 'callback_data': 'start_status'}
            }

            result = app._create_thread_payload(-1001234567890, "body", "header", "5312241539987020022", "firing")

            expected = {
                'chat_id': -1001234567890,
                'text': '🔥 header\nbody',
                'parse_mode': 'HTML',
                'reply_markup': {
                    'inline_keyboard': [
                        [
                            {'text': 'Take It', 'callback_data': 'start_chain'},
                            {'text': 'Status', 'callback_data': 'start_status'}
                        ]
                    ]
                }
            }
            assert result == expected

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

    def test_update_thread_payload(self, app_config, channels, users):
        """Test update_thread_payload method."""
        app = self.create_telegram_app(app_config, channels, users)

        with patch('app.im.telegram.telegram_application.buttons') as mock_buttons:
            mock_buttons.__getitem__.return_value = {
                'takeit': {'text': 'Take It', 'callback_data': 'start_chain'},
                'release': {'text': 'Release', 'callback_data': 'stop_chain'},
                'enabled': {'text': 'Status', 'callback_data': 'start_status'},
                'disabled': {'text': 'Status', 'callback_data': 'stop_status'}
            }

            result = app.update_thread_payload(-1001234567890, "123456/789012", "body", "header", "5312241539987020022",
                                               "firing", True, True)

            expected = {
                'chat_id': -1001234567890,
                'message_id': '789012',
                'text': '🔥 header\nbody',
                'parse_mode': 'HTML',
                'reply_markup': {
                    'inline_keyboard': [
                        [
                            {'text': 'Take It', 'callback_data': 'start_chain'},
                            {'text': 'Status', 'callback_data': 'start_status'}
                        ]
                    ]
                }
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

    @pytest.mark.asyncio
    async def test_buttons_handler_chain_action_assigned(self, app_config, channels, users):
        """Test buttons_handler with chain action when user is already assigned."""
        app = self.create_telegram_app(app_config, channels, users)

        # Mock incident
        incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="firing"
        )
        incident.assigned_user_id = 123456789
        incident.chain_enabled = True

        # Mock incidents collection
        incidents = create_mock_incidents_collection()
        incidents.get_by_ts.return_value = incident

        # Mock queue
        queue = create_mock_queue()

        # Mock route
        route = create_mock_route()

        payload = {
            "callback_query": {
                "id": "test_callback_id",
                "message": {
                    "message_id": 123,
                    "message_thread_id": 456
                },
                "data": "stop_chain",
                "from": {
                    "id": 123456789,
                    "first_name": "Test",
                    "last_name": "User"
                }
            }
        }

        async with create_telegram_buttons_handler_context(
            app, payload, incidents, queue, route,
            expected_log_message='Incident test-uuid -> button TAKE IT pressed, but user is already assigned'
        ) as (result, mock_logger, _):
            pass  # All assertions are handled by the context manager

    @pytest.mark.asyncio
    async def test_buttons_handler_chain_action_assign(self, app_config, channels, users):
        """Test buttons_handler with chain action to assign user."""
        app = self.create_telegram_app(app_config, channels, users)

        # Mock incident
        incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="firing"
        )
        incident.assigned_user_id = "other_user"
        incident.chain_enabled = True
        incident.assign_user_id = Mock()
        incident.assign_user = Mock()

        # Mock incidents collection
        incidents = create_mock_incidents_collection()
        incidents.get_by_ts.return_value = incident

        # Mock queue
        queue = create_mock_queue()

        # Mock route
        route = create_mock_route()

        payload = {
            "callback_query": {
                "id": "test_callback_id",
                "message": {
                    "message_id": 123,
                    "message_thread_id": 456
                },
                "data": "stop_chain",
                "from": {
                    "id": 123456789,
                    "first_name": "Test",
                    "last_name": "User"
                }
            }
        }

        async with create_telegram_buttons_handler_context(
            app, payload, incidents, queue, route,
            expected_log_message='Incident test-uuid -> button TAKE IT pressed, assigning to 123456789',
            additional_patches={
                'post_assignment_notification': Mock(),
                'fetch_and_assign_user_name': Mock()
            }
        ) as (result, mock_logger, patch_objects):
            patch_objects['post_assignment_notification'].assert_called_once()
            patch_objects['fetch_and_assign_user_name'].assert_called_once()

    @pytest.mark.asyncio
    async def test_buttons_handler_chain_action_release(self, app_config, channels, users):
        """Test buttons_handler with chain action to release incident."""
        app = self.create_telegram_app(app_config, channels, users)

        # Mock incident
        incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="resolved"
        )
        incident.chain_enabled = False
        incident.release = Mock()

        # Mock incidents collection
        incidents = create_mock_incidents_collection()
        incidents.get_by_ts.return_value = incident

        # Mock queue
        queue = create_mock_queue()

        # Mock route
        route = create_mock_route()

        payload = {
            "callback_query": {
                "id": "test_callback_id",
                "message": {
                    "message_id": 123,
                    "message_thread_id": 456
                },
                "data": "start_chain",
                "from": {
                    "id": 123456789,
                    "first_name": "Test",
                    "last_name": "User"
                }
            }
        }

        async with create_telegram_buttons_handler_context(
            app, payload, incidents, queue, route,
            expected_log_message='Incident test-uuid -> button RELEASE pressed',
            additional_patches={
                'post_unassignment_notification': Mock()
            }
        ) as (result, mock_logger, patch_objects):
            patch_objects['post_unassignment_notification'].assert_called_once()
            incident.release.assert_called_once()

    @pytest.mark.asyncio
    async def test_buttons_handler_status_action_enable(self, app_config, channels, users):
        """Test buttons_handler with status action to enable status."""
        app = self.create_telegram_app(app_config, channels, users)

        # Mock incident
        incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="firing"
        )
        incident.status_enabled = False

        # Mock incidents collection
        incidents = create_mock_incidents_collection()
        incidents.get_by_ts.return_value = incident

        # Mock queue
        queue = create_mock_queue()

        # Mock route
        route = create_mock_route()

        payload = {
            "callback_query": {
                "id": "test_callback_id",
                "message": {
                    "message_id": 123,
                    "message_thread_id": 456
                },
                "data": "start_status",
                "from": {
                    "id": 123456789,
                    "first_name": "Test",
                    "last_name": "User"
                }
            }
        }

        async with create_telegram_buttons_handler_context(
            app, payload, incidents, queue, route,
            expected_log_message='Incident test-uuid -> button STATUS pressed (enabled)'
        ) as (result, mock_logger, _):
            assert incident.status_enabled is True

    @pytest.mark.asyncio
    async def test_buttons_handler_status_action_disable(self, app_config, channels, users):
        """Test buttons_handler with status action to disable status."""
        app = self.create_telegram_app(app_config, channels, users)

        # Mock incident
        incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="firing"
        )
        incident.status_enabled = True

        # Mock incidents collection
        incidents = create_mock_incidents_collection()
        incidents.get_by_ts.return_value = incident

        # Mock queue
        queue = create_mock_queue()

        # Mock route
        route = create_mock_route()

        payload = {
            "callback_query": {
                "id": "test_callback_id",
                "message": {
                    "message_id": 123,
                    "message_thread_id": 456
                },
                "data": "stop_status",
                "from": {
                    "id": 123456789,
                    "first_name": "Test",
                    "last_name": "User"
                }
            }
        }

        async with create_telegram_buttons_handler_context(
            app, payload, incidents, queue, route,
            expected_log_message='Incident test-uuid -> button STATUS pressed (disabled)'
        ) as (result, mock_logger, _):
            assert incident.status_enabled is False

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

        with patch.object(app, '_setup_webhook') as mock_setup_webhook:
            mock_setup_webhook.return_value = AsyncMock()

            await app.initialize_async()

            mock_setup_webhook.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_http_interaction(self, app_config, channels, users):
        """Test send_message method with HTTP interaction."""
        app = self.create_telegram_app(app_config, channels, users)

        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={'result': {'message_id': 12345}})
        mock_response.close = Mock()

        with patch.object(app.http, 'post', new=AsyncMock(return_value=mock_response)) as mock_post:
            result = await app.send_message("test_channel", "test message", None)

            assert result == 12345
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_thread_http_interaction(self, app_config, channels, users):
        """Test create_thread method with HTTP interaction."""
        app = self.create_telegram_app(app_config, channels, users)

        # Mock HTTP responses
        mock_topic_response = AsyncMock()
        mock_topic_response.json = AsyncMock(return_value={'result': {'message_thread_id': 67890}})
        mock_topic_response.close = Mock()

        mock_thread_response = AsyncMock()
        mock_thread_response.json = AsyncMock(return_value={'result': {'message_id': 12345}})
        mock_thread_response.close = Mock()

        mock_post = AsyncMock(side_effect=[mock_topic_response, mock_thread_response])
        with patch.object(app.http, 'post', new=mock_post):
            result = await app.create_thread("test_channel", "body", "header", "icon", "status")

            assert result == "67890/12345"
            assert mock_post.call_count == 2

    @pytest.mark.asyncio
    async def test_send_create_thread_http_interaction(self, app_config, channels, users):
        """Test _send_create_thread method with HTTP interaction."""
        app = self.create_telegram_app(app_config, channels, users)

        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={'result': {'message_id': 12345}})
        mock_response.close = Mock()

        with patch.object(app.http, 'post', new=AsyncMock(return_value=mock_response)) as mock_post:
            result = await app._send_create_thread({'test': 'payload'})

            assert result == 12345
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_topic_success(self, app_config, channels, users):
        """Test _create_topic method with successful HTTP response."""
        app = self.create_telegram_app(app_config, channels, users)

        # Mock successful HTTP response
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={'result': {'message_thread_id': 67890}})
        mock_response.close = Mock()

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
    async def test_update_thread_with_status_enabled(self, app_config, channels, users):
        """Test update_thread method when status is enabled."""
        app = self.create_telegram_app(app_config, channels, users)

        with patch.object(app, '_update_topic') as mock_update_topic, \
                patch.object(app, 'update_thread_payload') as mock_payload, \
                patch.object(app, '_update_thread') as mock_update:
            mock_payload.return_value = {'test': 'payload'}
            mock_update_topic.return_value = AsyncMock()
            mock_update.return_value = AsyncMock()

            await app.update_thread("channel", "123/456", "firing", "body", "header", "icon", True, True)

            mock_update_topic.assert_called_once_with("channel", "123/456", "header", "icon")
            mock_payload.assert_called_once()
            mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_thread_with_status_disabled(self, app_config, channels, users):
        """Test update_thread method when status is disabled."""
        app = self.create_telegram_app(app_config, channels, users)

        with patch.object(app, '_update_topic') as mock_update_topic, \
                patch.object(app, 'update_thread_payload') as mock_payload, \
                patch.object(app, '_update_thread') as mock_update:
            mock_payload.return_value = {'test': 'payload'}
            mock_update_topic.return_value = AsyncMock()
            mock_update.return_value = AsyncMock()

            await app.update_thread("channel", "123/456", "firing", "body", "header", "icon", True, False)

            # Should use question mark icon when status is disabled
            mock_update_topic.assert_called_once_with("channel", "123/456", "header", "5377316857231450742")
            mock_payload.assert_called_once()
            mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_thread_with_closed_status(self, app_config, channels, users):
        """Test update_thread method when status is closed."""
        app = self.create_telegram_app(app_config, channels, users)

        with patch.object(app, '_update_topic') as mock_update_topic, \
                patch.object(app, 'update_thread_payload') as mock_payload, \
                patch.object(app, '_update_thread') as mock_update:
            mock_payload.return_value = {'test': 'payload'}
            mock_update_topic.return_value = AsyncMock()
            mock_update.return_value = AsyncMock()

            await app.update_thread("channel", "123/456", "closed", "body", "header", "icon", True, True)

            # Should use original icon when status is closed (because status_enabled=True OR status=closed)
            mock_update_topic.assert_called_once_with("channel", "123/456", "header", "icon")
            mock_payload.assert_called_once()
            mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_topic_success(self, app_config, channels, users):
        """Test _update_topic method with successful HTTP response."""
        app = self.create_telegram_app(app_config, channels, users)

        # Mock successful HTTP response
        mock_response = AsyncMock()
        mock_response.close = Mock()

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
        mock_response = AsyncMock()
        mock_response.close = Mock()

        with patch.object(app.http, 'post', new=AsyncMock(return_value=mock_response)) as mock_post:
            await app._update_thread("123/456", {'test': 'payload'})

            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_thread_http_error_handling(self, app_config, channels, users):
        """Test _update_thread method with HTTP error."""
        app = self.create_telegram_app(app_config, channels, users)

        with patch.object(app.http, 'post') as mock_post:
            mock_post.side_effect = aiohttp.ClientError("Connection failed")

            # Should not raise exception, just log error
            await app._update_thread("123/456", {'test': 'payload'})

    @pytest.mark.asyncio
    async def test_get_user_details_success(self, app_config, channels, users):
        """Test get_user_details method with successful HTTP response."""
        app = self.create_telegram_app(app_config, channels, users)

        # Mock successful HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            'ok': True,
            'result': {
                'first_name': 'John',
                'last_name': 'Doe',
                'username': 'johndoe'
            }
        })
        mock_response.close = Mock()

        with patch.object(app.http, 'get', new=AsyncMock(return_value=mock_response)):
            result = await app.get_user_details({'id': '123456'})

            assert result == {
                'id': '123456',
                'exists': True,
                'full_name': 'John Doe',
                'username': 'John Doe'
            }

    @pytest.mark.asyncio
    async def test_get_user_details_http_error(self, app_config, channels, users):
        """Test get_user_details method with HTTP error."""
        app = self.create_telegram_app(app_config, channels, users)

        # Mock HTTP error response
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.close = Mock()

        with patch.object(app.http, 'get', new=AsyncMock(return_value=mock_response)):
            result = await app.get_user_details({'id': '123456'})

            assert result == {
                'id': '123456',
                'exists': False,
                'full_name': None,
                'username': None
            }

    @pytest.mark.asyncio
    async def test_get_user_details_api_error(self, app_config, channels, users):
        """Test get_user_details method with API error response."""
        app = self.create_telegram_app(app_config, channels, users)

        # Mock API error response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            'ok': False,
            'description': 'User not found'
        })
        mock_response.close = Mock()

        with patch.object(app.http, 'get', new=AsyncMock(return_value=mock_response)):
            result = await app.get_user_details({'id': '123456'})

            assert result == {
                'id': '123456',
                'exists': False,
                'full_name': None,
                'username': None
            }

    @pytest.mark.asyncio
    async def test_setup_webhook_success(self, app_config, channels, users):
        """Test _setup_webhook method with successful HTTP response."""
        app = self.create_telegram_app(app_config, channels, users)

        # Mock successful HTTP response
        mock_response = AsyncMock()
        mock_response.close = Mock()

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
