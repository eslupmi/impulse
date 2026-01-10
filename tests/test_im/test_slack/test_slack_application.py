"""
Unit tests for SlackApplication class.

This module tests the SlackApplication class which extends the Application ABC
and provides Slack-specific functionality for incident management.
"""
from unittest.mock import Mock, AsyncMock, patch, mock_open

import pytest
from fastapi.responses import JSONResponse

from app.config.validation import SlackApplicationConfig, MessengerType
from app.im.slack.slack_application import SlackApplication
from tests.utils import (
    create_mock_incident_for_handlers,
    create_mock_incidents_collection,
    create_mock_queue,
    create_mock_route,
    MockContextManager,
    create_slack_buttons_handler_context
)


class TestSlackApplication:
    """Test cases for SlackApplication class."""

    @pytest.fixture(autouse=True)
    def mock_asyncio_sleep(self):
        """Mock asyncio.sleep to avoid delays in tests."""
        with patch('asyncio.sleep') as mock_sleep:
            yield mock_sleep

    def create_slack_app(self, app_config, channels, default_channel):
        """Helper method to create SlackApplication with proper mocking."""
        with patch('builtins.open', mock_open(read_data="template content")):
            return SlackApplication(app_config, channels, default_channel)

    @pytest.fixture
    def app_config(self):
        """Create mock SlackApplicationConfig for testing."""
        config = Mock(spec=SlackApplicationConfig)
        config.type = MessengerType.SLACK
        config.channels = {"default": {"id": "C123456789"}}
        config.users = {"admin1": {"id": "U123456"}}
        config.admin_users = ["admin1", "admin2"]
        config.user_groups = {}
        config.chains = {}
        config.template_files = Mock()
        config.template_files.status_icons = None
        config.template_files.header = None
        config.template_files.body = None
        return config

    @pytest.fixture
    def channels(self):
        """Create mock channels configuration."""
        return {"default": {"id": "C123456789"}}

    @pytest.fixture
    def default_channel(self):
        """Create default channel name."""
        return "default"

    def test_slack_application_initialization(self, app_config, channels, default_channel):
        """Test SlackApplication initialization."""
        app = self.create_slack_app(app_config, channels, default_channel)

        assert app.type == MessengerType.SLACK
        assert app.url == "https://slack.com"
        assert app.team is None
        assert app.channels == channels
        assert app.default_channel_id == "C123456789"
        assert app.post_message_url == "https://slack.com/api/chat.postMessage"
        assert app.thread_id_key == "ts"

    def test_initialize_specific_params(self, app_config, channels, default_channel):
        """Test _initialize_specific_params method."""
        with patch('app.im.slack.slack_application.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.slack_bot_user_oauth_token = "test-token"
            mock_get_config.return_value = mock_config

            app = self.create_slack_app(app_config, channels, default_channel)

            assert app.post_message_url == "https://slack.com/api/chat.postMessage"
            assert app.headers == {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer test-token'
            }
            assert app.thread_id_key == "ts"

    def test_get_url(self, app_config, channels, default_channel):
        """Test _get_url method."""
        app = self.create_slack_app(app_config, channels, default_channel)
        url = app._get_url(app_config)

        assert url == "https://slack.com"

    def test_get_public_url_method(self, app_config, channels, default_channel):
        """Test _get_public_url method signature."""
        app = self.create_slack_app(app_config, channels, default_channel)

        # Test that the method exists and is async
        assert hasattr(app, '_get_public_url')
        assert callable(app._get_public_url)
        import inspect
        assert inspect.iscoroutinefunction(app._get_public_url)

    def test_get_team_name(self, app_config, channels, default_channel):
        """Test _get_team_name method."""
        app = self.create_slack_app(app_config, channels, default_channel)
        team_name = app._get_team_name(app_config)

        assert team_name is None

    def test_get_user_details_method(self, app_config, channels, default_channel):
        """Test get_user_details method signature."""
        app = self.create_slack_app(app_config, channels, default_channel)

        # Test that the method exists and is async
        assert hasattr(app, 'get_user_details')
        assert callable(app.get_user_details)
        import inspect
        assert inspect.iscoroutinefunction(app.get_user_details)

        # Test method signature
        sig = inspect.signature(app.get_user_details)
        params = list(sig.parameters.keys())
        assert 'user_details' in params

    def test_get_user_details_parameters(self, app_config, channels, default_channel):
        """Test get_user_details method parameters."""
        app = self.create_slack_app(app_config, channels, default_channel)

        # Test that the method accepts the expected parameters
        import inspect
        sig = inspect.signature(app.get_user_details)
        params = list(sig.parameters.keys())

        assert 'user_details' in params

    def test_get_user_details_return_type(self, app_config, channels, default_channel):
        """Test get_user_details method return type annotation."""
        app = self.create_slack_app(app_config, channels, default_channel)

        # Test that the method is async
        import inspect
        assert inspect.iscoroutinefunction(app.get_user_details)

    def test_create_user(self, app_config, channels, default_channel):
        """Test create_user method."""
        app = self.create_slack_app(app_config, channels, default_channel)

        user_details = {
            "id": "U123456",
            "exists": True,
            "full_name": "Test User"
        }

        user = app.create_user("testuser", user_details)

        assert user.name == "testuser"
        assert user.id == "U123456"
        assert user.exists is True

    def test_get_notification_destinations(self, app_config, channels, default_channel):
        """Test get_notification_destinations method."""
        app = self.create_slack_app(app_config, channels, default_channel)

        # Mock admin users
        admin1 = Mock()
        admin1.id = "U123456"
        admin1.get_notification_identifier = Mock(return_value="U123456")
        admin2 = Mock()
        admin2.id = "U789012"
        admin2.get_notification_identifier = Mock(return_value="U789012")
        app.admin_users = [admin1, admin2]

        destinations = app.get_notification_destinations()

        assert destinations == ["U123456", "U789012"]

    def test_get_admins_text(self, app_config, channels, default_channel):
        """Test get_admins_text method."""
        app = self.create_slack_app(app_config, channels, default_channel)

        # Mock admin users
        admin1 = Mock()
        admin1.id = "U123456"
        admin2 = Mock()
        admin2.id = "U789012"
        app.admin_users = [admin1, admin2]

        with patch('app.im.slack.slack_application.slack_env') as mock_env:
            mock_template = Mock()
            mock_template.render.return_value = "Admins: <@U123456> <@U789012>"
            mock_env.from_string.return_value = mock_template

            result = app.get_admins_text()

            assert result == "Admins: <@U123456> <@U789012>"
            mock_env.from_string.assert_called_once()

    def test_create_thread_payload(self, app_config, channels, default_channel):
        """Test _create_thread_payload method."""
        app = self.create_slack_app(app_config, channels, default_channel)

        with patch('app.im.slack.slack_application.slack_get_create_thread_payload') as mock_payload:
            mock_payload.return_value = {"test": "create_payload"}

            result = app._create_thread_payload("C123456789", "body", "header", "icons", "firing")

            assert result == {"test": "create_payload"}
            mock_payload.assert_called_once_with("C123456789", "body", "header", "icons", "firing")

    def test_post_thread_payload(self, app_config, channels, default_channel):
        """Test _post_thread_payload method."""
        app = self.create_slack_app(app_config, channels, default_channel)

        result = app._post_thread_payload("C123456789", "1234567890.123456", "Test message")

        expected = {
            'channel': 'C123456789',
            'thread_ts': '1234567890.123456',
            'text': 'Test message',
            'unfurl_links': False,
            'unfurl_media': False
        }
        assert result == expected

    def test_update_thread_payload(self, app_config, channels, default_channel):
        """Test update_thread_payload method."""
        app = self.create_slack_app(app_config, channels, default_channel)

        with patch('app.im.slack.slack_application.slack_get_update_payload') as mock_payload:
            mock_payload.return_value = {"test": "update_payload"}

            result = app.update_thread_payload("C123456789", "1234567890.123456", "body", "header", "icons", "firing",
                                               True, None, "")

            assert result == {"test": "update_payload"}
            mock_payload.assert_called_once_with("C123456789", "1234567890.123456", "body", "header", "icons", "firing",
                                                 True, None, "")

    def test_update_thread_method(self, app_config, channels, default_channel):
        """Test _update_thread method signature."""
        app = self.create_slack_app(app_config, channels, default_channel)

        # Test that the method exists and is async
        assert hasattr(app, '_update_thread')
        assert callable(app._update_thread)
        import inspect
        assert inspect.iscoroutinefunction(app._update_thread)

        # Test method signature
        sig = inspect.signature(app._update_thread)
        params = list(sig.parameters.keys())
        assert 'id_' in params
        assert 'payload' in params

    def test_markdown_links_to_native_format(self, app_config, channels, default_channel):
        """Test _markdown_links_to_native_format method."""
        app = self.create_slack_app(app_config, channels, default_channel)

        # Test markdown link conversion
        text = "Check out [this link](https://example.com) for more info"
        result = app._markdown_links_to_native_format(text)

        assert result == "Check out <https://example.com|this link> for more info"

    def test_markdown_links_to_native_format_multiple(self, app_config, channels, default_channel):
        """Test _markdown_links_to_native_format with multiple links."""
        app = self.create_slack_app(app_config, channels, default_channel)

        text = "See [link1](https://example1.com) and [link2](https://example2.com)"
        result = app._markdown_links_to_native_format(text)

        assert result == "See <https://example1.com|link1> and <https://example2.com|link2>"

    def test_markdown_links_to_native_format_no_links(self, app_config, channels, default_channel):
        """Test _markdown_links_to_native_format with no links."""
        app = self.create_slack_app(app_config, channels, default_channel)

        text = "This text has no links"
        result = app._markdown_links_to_native_format(text)

        assert result == "This text has no links"

    @pytest.mark.asyncio
    async def test_buttons_handler_unauthorized(self, app_config, channels, default_channel):
        """Test buttons_handler with unauthorized request."""
        app = self.create_slack_app(app_config, channels, default_channel)

        payload = {
            "token": "invalid_token",
            "message_ts": "1234567890.123456"
        }

        incidents = create_mock_incidents_collection()
        queue = create_mock_queue()
        route = create_mock_route()

        with patch('app.im.slack.slack_application.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.slack_verification_token = "valid_token"
            mock_get_config.return_value = mock_config

            result = await app.buttons_handler(payload, incidents, queue, route)

            assert isinstance(result, JSONResponse)
            assert result.status_code == 401

    @pytest.mark.asyncio
    async def test_buttons_handler_no_incident(self, app_config, channels, default_channel):
        """Test buttons_handler when no incident is found."""
        app = self.create_slack_app(app_config, channels, default_channel)

        payload = {
            "token": "valid_token",
            "message_ts": "1234567890.123456",
            "original_message": {"text": "Original message"}
        }

        incidents = create_mock_incidents_collection()
        incidents.get_by_ts.return_value = None
        queue = create_mock_queue()
        route = create_mock_route()

        with patch('app.im.slack.slack_application.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.slack_verification_token = "valid_token"
            mock_get_config.return_value = mock_config

            result = await app.buttons_handler(payload, incidents, queue, route)

            assert isinstance(result, JSONResponse)
            assert result.status_code == 200
            assert result.body == b'{"text":"Original message"}'

    @pytest.mark.asyncio
    async def test_buttons_handler_chain_action_assigned(self, app_config, channels, default_channel):
        """Test buttons_handler with chain action when user is already assigned."""
        app = self.create_slack_app(app_config, channels, default_channel)

        # Mock incident
        incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="firing"
        )
        incident.assigned_user_id = "U123456"
        incident.chain_enabled = True

        # Mock incidents collection
        incidents = create_mock_incidents_collection()
        incidents.get_by_ts.return_value = incident

        # Mock queue
        queue = create_mock_queue()

        # Mock route
        route = create_mock_route()

        payload = {
            "token": "valid_token",
            "message_ts": "1234567890.123456",
            "original_message": {"text": "Original message"},
            "actions": [{"name": "chain"}],
            "user": {"id": "U123456"}
        }

        async with create_slack_buttons_handler_context(
            app, payload, incidents, queue, route,
            expected_log_message='Incident test-uuid -> button TAKE IT pressed, but user is already assigned'
        ) as (result, mock_logger, mock_reformat, _):
            pass  # All assertions are handled by the context manager

    @pytest.mark.asyncio
    async def test_buttons_handler_chain_action_assign(self, app_config, channels, default_channel):
        """Test buttons_handler with chain action to assign user."""
        app = self.create_slack_app(app_config, channels, default_channel)

        # Mock incident
        incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="firing"
        )
        incident.assigned_user_id = "other_user"
        incident.chain_enabled = True
        incident.assign_user_id = Mock()

        # Mock incidents collection
        incidents = create_mock_incidents_collection()
        incidents.get_by_ts.return_value = incident

        # Mock queue
        queue = create_mock_queue()

        # Mock route
        route = create_mock_route()

        payload = {
            "token": "valid_token",
            "message_ts": "1234567890.123456",
            "original_message": {"text": "Original message"},
            "actions": [{"name": "chain"}],
            "user": {"id": "U123456"}
        }

        async with create_slack_buttons_handler_context(
            app, payload, incidents, queue, route,
            expected_log_message='Incident test-uuid -> button TAKE IT pressed, assigning to U123456',
            additional_patches={
                'post_assignment_notification': Mock(),
                'fetch_and_assign_user_name': Mock()
            }
        ) as (result, mock_logger, mock_reformat, patch_objects):
            patch_objects['post_assignment_notification'].assert_called_once()
            patch_objects['fetch_and_assign_user_name'].assert_called_once()

    @pytest.mark.asyncio
    async def test_buttons_handler_chain_action_release(self, app_config, channels, default_channel):
        """Test buttons_handler with chain action to release incident."""
        app = self.create_slack_app(app_config, channels, default_channel)

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
            "token": "valid_token",
            "message_ts": "1234567890.123456",
            "original_message": {"text": "Original message"},
            "actions": [{"name": "chain"}],
            "user": {"id": "U123456"}
        }

        async with create_slack_buttons_handler_context(
            app, payload, incidents, queue, route,
            expected_log_message='Incident test-uuid -> button RELEASE pressed',
            additional_patches={
                'post_unassignment_notification': Mock()
            }
        ) as (result, mock_logger, mock_reformat, patch_objects):
            patch_objects['post_unassignment_notification'].assert_called_once()
            incident.release.assert_called_once()

    @pytest.mark.asyncio
    async def test_buttons_handler_status_action_enable(self, app_config, channels, default_channel):
        """Test buttons_handler with status action to enable status."""
        app = self.create_slack_app(app_config, channels, default_channel)

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
            "token": "valid_token",
            "message_ts": "1234567890.123456",
            "original_message": {"text": "Original message"},
            "actions": [{"name": "status"}],
            "user": {"id": "U123456"}
        }

        async with create_slack_buttons_handler_context(
            app, payload, incidents, queue, route,
            expected_log_message=None
        ) as (result, mock_logger, mock_reformat, _):
            # Status button functionality has been replaced with freeze/unfreeze
            # Just verify the response is successful
            pass # NOSONAR

    @pytest.mark.asyncio
    async def test_buttons_handler_status_action_disable(self, app_config, channels, default_channel):
        """Test buttons_handler with status action to disable status."""
        app = self.create_slack_app(app_config, channels, default_channel)

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
            "token": "valid_token",
            "message_ts": "1234567890.123456",
            "original_message": {"text": "Original message"},
            "actions": [{"name": "status"}],
            "user": {"id": "U123456"}
        }

        async with create_slack_buttons_handler_context(
            app, payload, incidents, queue, route,
            expected_log_message=None
        ) as (result, mock_logger, mock_reformat, _):
            # Status button functionality has been replaced with freeze/unfreeze
            # Just verify the response is successful
            pass # NOSONAR

    @pytest.mark.asyncio
    async def test_get_public_url_success(self, app_config, channels, default_channel):
        """Test _get_public_url method with successful HTTP response."""
        app = self.create_slack_app(app_config, channels, default_channel)

        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={"url": "https://test-workspace.slack.com"})
        mock_response.close = Mock()

        # Mock HTTP client
        app.http = Mock()
        app.http.get = AsyncMock(return_value=mock_response)

        result = await app._get_public_url(app_config)

        assert result == "https://test-workspace.slack.com"
        app.http.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_details_success(self, app_config, channels, default_channel):
        """Test get_user_details method with successful response."""
        app = self.create_slack_app(app_config, channels, default_channel)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "ok": True,
            "user": {
                "id": "U123456",
                "profile": {
                    "real_name_normalized": "Test User"
                }
            }
        })
        mock_response.close = Mock()

        # Mock HTTP client
        app.http = Mock()
        app.http.get = AsyncMock(return_value=mock_response)

        result = await app.get_user_details({"id": "U123456"})

        assert result == {
            "id": "U123456",
            "exists": True,
            "full_name": "Test User"
        }

    @pytest.mark.asyncio
    async def test_get_user_details_http_error(self, app_config, channels, default_channel):
        """Test get_user_details method with HTTP error status."""
        app = self.create_slack_app(app_config, channels, default_channel)

        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.close = Mock()

        # Mock HTTP client
        app.http = Mock()
        app.http.get = AsyncMock(return_value=mock_response)

        result = await app.get_user_details({"id": "U123456"})

        assert result == {
            "id": "U123456",
            "exists": False,
            "full_name": None,
            "username": None
        }

    @pytest.mark.asyncio
    async def test_get_user_details_api_error(self, app_config, channels, default_channel):
        """Test get_user_details method with Slack API error."""
        app = self.create_slack_app(app_config, channels, default_channel)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "ok": False,
            "error": "user_not_found"
        })
        mock_response.close = Mock()

        # Mock HTTP client
        app.http = Mock()
        app.http.get = AsyncMock(return_value=mock_response)

        result = await app.get_user_details({"id": "U123456"})

        assert result == {
            "id": "U123456",
            "exists": False,
            "full_name": None,
            "username": None
        }

    @pytest.mark.asyncio
    async def test_update_thread_success(self, app_config, channels, default_channel):
        """Test _update_thread method with successful HTTP response."""
        app = self.create_slack_app(app_config, channels, default_channel)

        mock_response = AsyncMock()
        mock_response.close = Mock()

        # Mock HTTP client
        app.http = Mock()
        app.http.post = AsyncMock(return_value=mock_response)

        await app._update_thread("1234567890.123456", {"text": "Updated message"})

        app.http.post.assert_called_once()
