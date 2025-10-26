"""
Unit tests for app.im.mattermost.mattermost_application module.
"""
import asyncio
from unittest.mock import Mock, AsyncMock, patch, mock_open

import pytest
from fastapi.responses import JSONResponse

from app.im.mattermost.mattermost_application import MattermostApplication
from app.config.validation import ApplicationConfig, MattermostUser, MessengerType
from tests.utils import (
    create_mock_application, create_mock_incident_for_handlers, 
    create_mock_queue, create_mock_incidents_collection,
    create_mock_route, create_test_datetime, MockContextManager
)


class TestMattermostApplication:
    """Test cases for MattermostApplication class."""

    @pytest.fixture(autouse=True)
    def mock_asyncio_sleep(self):
        """Mock asyncio.sleep to avoid delays in tests."""
        with patch('asyncio.sleep') as mock_sleep:
            yield mock_sleep

    def setup_method(self):
        """Setup for each test method."""
        self.app_config = Mock(spec=ApplicationConfig)
        self.app_config.type = MessengerType.MATTERMOST
        self.app_config.address = "https://mattermost.example.com"
        self.app_config.team = "test-team"
        self.app_config.impulse_address = "https://impulse.example.com"
        self.app_config.chains = {}
        self.app_config.template_files = {}
        self.app_config.users = {}
        self.app_config.user_groups = {}
        self.app_config.admin_users = []
        
        self.channels = {"default": {"id": "channel123"}}
        self.default_channel = "default"

    def test_mattermost_application_initialization(self):
        """Test MattermostApplication initialization."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        assert app.type == MessengerType.MATTERMOST
        assert app.url == "https://mattermost.example.com"
        assert app.team == "test-team"
        assert app.post_message_url == "https://mattermost.example.com/api/v4/posts"
        assert app.thread_id_key == "id"
        assert app.post_delay is not None
        assert app.headers is not None
        assert "Authorization" in app.headers
        assert "Content-Type" in app.headers

    def test_get_url(self):
        """Test _get_url method."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        url = app._get_url(self.app_config)
        
        assert url == "https://mattermost.example.com"

    def test_get_public_url(self):
        """Test _get_public_url method."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        public_url = app._get_public_url(self.app_config)
        
        assert public_url == "https://mattermost.example.com"

    def test_get_team_name(self):
        """Test _get_team_name method."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        team_name = app._get_team_name(self.app_config)
        
        assert team_name == "test-team"

    def test_get_user_details_method_exists(self):
        """Test that get_user_details method exists and is callable."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        # Test that the method exists and is callable
        assert hasattr(app, 'get_user_details')
        assert callable(app.get_user_details)

    def test_get_user_details_parameters(self):
        """Test get_user_details method parameters."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        # Test that the method accepts the expected parameters
        import inspect
        sig = inspect.signature(app.get_user_details)
        params = list(sig.parameters.keys())
        
        assert 'user_details' in params

    def test_get_user_details_return_type(self):
        """Test get_user_details method return type annotation."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        # Test that the method is async
        import inspect
        assert inspect.iscoroutinefunction(app.get_user_details)

    def test_create_user(self):
        """Test create_user method."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        user_details = {
            "id": "user123",
            "username": "testuser",
            "exists": True
        }
        
        user = app.create_user("testuser", user_details)
        
        assert user.name == "testuser"
        assert user.id == "user123"
        assert user.username == "testuser"
        assert user.exists is True

    def test_get_notification_destinations(self):
        """Test get_notification_destinations method."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        # Mock admin users
        admin1 = Mock()
        admin1.username = "admin1"
        admin2 = Mock()
        admin2.username = "admin2"
        app.admin_users = [admin1, admin2]
        
        destinations = app.get_notification_destinations()
        
        assert destinations == ["admin1", "admin2"]

    def test_format_text_bold(self):
        """Test format_text_bold method."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        with patch('app.im.mattermost.mattermost_application.mattermost_bold_text') as mock_bold:
            mock_bold.return_value = "**bold text**"
            result = app.format_text_bold("bold text")
            
            assert result == "**bold text**"
            mock_bold.assert_called_once_with("bold text")

    def test_format_text_italic(self):
        """Test format_text_italic method."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        result = app.format_text_italic("italic text")
        
        assert result == "_italic text_"

    def test_format_text_link(self):
        """Test _format_text_link method."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        result = app._format_text_link("link text", "https://example.com")
        
        assert result == "([link text](https://example.com))"

    def test_get_admins_text(self):
        """Test get_admins_text method."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        # Mock admin users
        admin1 = Mock()
        admin1.username = "admin1"
        admin2 = Mock()
        admin2.username = "admin2"
        app.admin_users = [admin1, admin2]
        
        with patch('app.im.mattermost.mattermost_application.mattermost_env') as mock_env:
            mock_template = Mock()
            mock_template.render.return_value = "Admins: @admin1, @admin2"
            mock_env.from_string.return_value = mock_template
            
            result = app.get_admins_text()
            
            assert result == "Admins: @admin1, @admin2"
            mock_env.from_string.assert_called_once()

    def test_send_message_method(self):
        """Test send_message method signature."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
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

    def test_create_thread_payload(self):
        """Test _create_thread_payload method."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        with patch('app.im.mattermost.mattermost_application.mattermost_get_create_thread_payload') as mock_payload:
            mock_payload.return_value = {"test": "payload"}
            
            result = app._create_thread_payload("channel123", "body", "header", "icons", "firing")
            
            assert result == {"test": "payload"}
            mock_payload.assert_called_once_with("channel123", "body", "header", "icons", "firing")

    def test_post_thread_payload(self):
        """Test _post_thread_payload method."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        result = app._post_thread_payload("channel123", "post123", "Test message")
        
        expected = {
            "channel_id": "channel123",
            "root_id": "post123",
            "message": "Test message"
        }
        assert result == expected

    def test_update_thread_payload(self):
        """Test update_thread_payload method."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        with patch('app.im.mattermost.mattermost_application.mattermost_get_update_payload') as mock_payload:
            mock_payload.return_value = {"test": "update_payload"}
            
            result = app.update_thread_payload("channel123", "post123", "body", "header", "icons", "firing", True, True)
            
            assert result == {"test": "update_payload"}
            mock_payload.assert_called_once_with("channel123", "post123", "body", "header", "icons", "firing", True, True)

    def test_update_thread_method(self):
        """Test _update_thread method signature."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
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

    def test_markdown_links_to_native_format(self):
        """Test _markdown_links_to_native_format method."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        result = app._markdown_links_to_native_format("Test text with [link](url)")
        
        # Mattermost doesn't modify markdown links
        assert result == "Test text with [link](url)"

    @pytest.mark.asyncio
    async def test_buttons_handler_chain_action_assigned(self):
        """Test buttons_handler with chain action when user is already assigned."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        # Mock incident
        incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="firing"
        )
        incident.assigned_user_id = "user123"
        
        # Mock incidents collection
        incidents = create_mock_incidents_collection()
        incidents.get_by_ts.return_value = incident
        
        # Mock queue
        queue = create_mock_queue()
        
        # Mock route
        route = create_mock_route()
        
        payload = {
            "post_id": "post123",
            "context": {"action": "chain"},
            "user_id": "user123",
            "user_name": "testuser"
        }
        
        with patch('app.im.mattermost.mattermost_application.logger') as mock_logger:
            result = await app.buttons_handler(payload, incidents, queue, route)
            
            assert isinstance(result, JSONResponse)
            assert result.status_code == 200
            mock_logger.info.assert_called_with(
                'Incident test-uuid -> button TAKE IT pressed, but user is already assigned'
            )

    @pytest.mark.asyncio
    async def test_buttons_handler_chain_action_assign(self):
        """Test buttons_handler with chain action to assign user."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        # Mock incident
        incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="firing"
        )
        incident.assigned_user_id = "other_user"
        
        # Mock incidents collection
        incidents = create_mock_incidents_collection()
        incidents.get_by_ts.return_value = incident
        
        # Mock queue
        queue = create_mock_queue()
        
        # Mock route
        route = create_mock_route()
        
        payload = {
            "post_id": "post123",
            "context": {"action": "chain"},
            "user_id": "user123",
            "user_name": "testuser"
        }
        
        with patch('app.im.mattermost.mattermost_application.logger') as mock_logger:
            with patch.object(app, 'post_assignment_notification') as mock_notification:
                with patch.object(app, 'fetch_and_assign_user_name') as mock_fetch:
                    # Mock templates to avoid Jinja2 errors
                    app.body_template = Mock()
                    app.body_template.form_message.return_value = "Test body"
                    app.header_template = Mock()
                    app.header_template.form_message.return_value = "Test header"
                    app.status_icons_template = Mock()
                    app.status_icons_template.form_message.return_value = "Test icons"
                    
                    result = await app.buttons_handler(payload, incidents, queue, route)
                    
                    assert isinstance(result, JSONResponse)
                    assert result.status_code == 200
                    mock_logger.info.assert_called_with(
                        'Incident test-uuid -> button TAKE IT pressed, assigning to user123'
                    )
                    mock_notification.assert_called_once()
                    mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_buttons_handler_chain_action_release(self):
        """Test buttons_handler with chain action to release incident."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        # Mock incident
        incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="resolved",
            chain_enabled=False
        )
        
        # Mock incidents collection
        incidents = create_mock_incidents_collection()
        incidents.get_by_ts.return_value = incident
        
        # Mock queue
        queue = create_mock_queue()
        
        # Mock route
        route = create_mock_route()
        
        payload = {
            "post_id": "post123",
            "context": {"action": "chain"},
            "user_id": "user123",
            "user_name": "testuser"
        }
        
        with patch('app.im.mattermost.mattermost_application.logger') as mock_logger:
            with patch.object(app, 'post_unassignment_notification') as mock_notification:
                # Mock templates to avoid Jinja2 errors
                app.body_template = Mock()
                app.body_template.form_message.return_value = "Test body"
                app.header_template = Mock()
                app.header_template.form_message.return_value = "Test header"
                app.status_icons_template = Mock()
                app.status_icons_template.form_message.return_value = "Test icons"
                
                result = await app.buttons_handler(payload, incidents, queue, route)
                
                assert isinstance(result, JSONResponse)
                assert result.status_code == 200
                mock_logger.info.assert_called_with(
                    'Incident test-uuid -> button RELEASE pressed'
                )
                mock_notification.assert_called_once()

    @pytest.mark.asyncio
    async def test_buttons_handler_status_action_enable(self):
        """Test buttons_handler with status action to enable status."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        # Mock incident
        incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="firing",
            status_enabled=False
        )
        
        # Mock incidents collection
        incidents = create_mock_incidents_collection()
        incidents.get_by_ts.return_value = incident
        
        # Mock queue
        queue = create_mock_queue()
        
        # Mock route
        route = create_mock_route()
        
        payload = {
            "post_id": "post123",
            "context": {"action": "status"},
            "user_id": "user123",
            "user_name": "testuser"
        }
        
        with patch('app.im.mattermost.mattermost_application.logger') as mock_logger:
            # Mock templates to avoid Jinja2 errors
            app.body_template = Mock()
            app.body_template.form_message.return_value = "Test body"
            app.header_template = Mock()
            app.header_template.form_message.return_value = "Test header"
            app.status_icons_template = Mock()
            app.status_icons_template.form_message.return_value = "Test icons"
            
            result = await app.buttons_handler(payload, incidents, queue, route)
            
            assert isinstance(result, JSONResponse)
            assert result.status_code == 200
            mock_logger.info.assert_called_with(
                'Incident test-uuid -> button STATUS pressed (enabled)'
            )
            assert incident.status_enabled is True

    @pytest.mark.asyncio
    async def test_buttons_handler_status_action_disable(self):
        """Test buttons_handler with status action to disable status."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        # Mock incident
        incident = create_mock_incident_for_handlers(
            uuid="test-uuid",
            status="firing",
            status_enabled=True
        )
        
        # Mock incidents collection
        incidents = create_mock_incidents_collection()
        incidents.get_by_ts.return_value = incident
        
        # Mock queue
        queue = create_mock_queue()
        
        # Mock route
        route = create_mock_route()
        
        payload = {
            "post_id": "post123",
            "context": {"action": "status"},
            "user_id": "user123",
            "user_name": "testuser"
        }
        
        with patch('app.im.mattermost.mattermost_application.logger') as mock_logger:
            # Mock templates to avoid Jinja2 errors
            app.body_template = Mock()
            app.body_template.form_message.return_value = "Test body"
            app.header_template = Mock()
            app.header_template.form_message.return_value = "Test header"
            app.status_icons_template = Mock()
            app.status_icons_template.form_message.return_value = "Test icons"
            
            result = await app.buttons_handler(payload, incidents, queue, route)
            
            assert isinstance(result, JSONResponse)
            assert result.status_code == 200
            mock_logger.info.assert_called_with(
                'Incident test-uuid -> button STATUS pressed (disabled)'
            )
            assert incident.status_enabled is False

    @pytest.mark.asyncio
    async def test_buttons_handler_no_incident(self):
        """Test buttons_handler when no incident is found."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        # Mock incidents collection
        incidents = create_mock_incidents_collection()
        incidents.get_by_ts.return_value = None
        
        # Mock queue
        queue = create_mock_queue()
        
        # Mock route
        route = create_mock_route()
        
        payload = {
            "post_id": "post123",
            "context": {"action": "chain"},
            "user_id": "user123",
            "user_name": "testuser"
        }
        
        result = await app.buttons_handler(payload, incidents, queue, route)
        
        assert isinstance(result, JSONResponse)
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_get_channels_success(self):
        """Test _get_channels method with successful HTTP response."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        # Mock HTTP response
        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock()
        mock_response.json = AsyncMock(return_value=[
            {"name": "general", "id": "channel1"},
            {"name": "incidents", "id": "channel2"}
        ])
        
        # Mock HTTP client
        app.http = Mock()
        app.http.get = Mock(return_value=MockContextManager(mock_response))
        
        result = await app._get_channels({"id": "team123"})
        
        assert result == {
            "general": {"name": "general", "id": "channel1"},
            "incidents": {"name": "incidents", "id": "channel2"}
        }
        app.http.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_channels_http_error(self):
        """Test _get_channels method with HTTP error."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        # Mock HTTP client to raise aiohttp.ClientError
        import aiohttp
        app.http = Mock()
        app.http.get = Mock(side_effect=aiohttp.ClientError("Connection error"))
        
        result = await app._get_channels({"id": "team123"})
        
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_user_details_success(self):
        """Test get_user_details method with successful response."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "id": "user123",
            "username": "testuser",
            "first_name": "Test",
            "last_name": "User"
        })
        
        # Mock HTTP client
        app.http = Mock()
        app.http.get = Mock(return_value=MockContextManager(mock_response))
        
        result = await app.get_user_details({"id": "user123"})
        
        assert result == {
            "id": "user123",
            "username": "testuser",
            "exists": True,
            "full_name": "Test User"
        }

    @pytest.mark.asyncio
    async def test_get_user_details_not_found(self):
        """Test get_user_details method with 404 response."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        mock_response = AsyncMock()
        mock_response.status = 404
        
        # Mock HTTP client
        app.http = Mock()
        app.http.get = Mock(return_value=MockContextManager(mock_response))
        
        result = await app.get_user_details({"id": "user123"})
        
        assert result == {
                "id": "user123",
                "username": None,
                "exists": False,
                "full_name": None
            }

    @pytest.mark.asyncio
    async def test_get_user_details_http_error(self):
        """Test get_user_details method with HTTP error status."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        mock_response = AsyncMock()
        mock_response.status = 500
        
        # Mock HTTP client
        app.http = Mock()
        app.http.get = Mock(return_value=MockContextManager(mock_response))
        
        result = await app.get_user_details({"id": "user123"})
        
        assert result == {
                "id": "user123",
                "username": None,
                "exists": False,
                "full_name": None
            }

    @pytest.mark.asyncio
    async def test_send_message_success(self):
        """Test send_message method with successful HTTP response."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value={"ts": "1234567890.123456"})
        
        # Mock HTTP client
        app.http = Mock()
        app.http.post = Mock(return_value=MockContextManager(mock_response))
        
        result = await app.send_message("channel123", "Test message", "Test attachment")
        
        assert result == "1234567890.123456"
        app.http.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_thread_success(self):
        """Test _update_thread method with successful HTTP response."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        
        mock_response = AsyncMock()
        
        # Mock HTTP client
        app.http = Mock()
        app.http.put = Mock(return_value=MockContextManager(mock_response))
        
        await app._update_thread("post123", {"message": "Updated message"})
        
        app.http.put.assert_called_once()
