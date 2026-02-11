"""
Unit tests for app.im.mattermost.mattermost_application module.
"""
from unittest.mock import Mock, AsyncMock, patch

import pytest
from fastapi.responses import JSONResponse

from app.config.validation import ApplicationConfig, MessengerType, MattermostApplicationConfig
from app.im.mattermost.mattermost_application import MattermostApplication
from tests.utils import (
    create_mock_incident_for_handlers,
    create_mock_queue, create_mock_incidents_collection,
    create_mock_route,
    create_mock_get_config_patch,
    create_mattermost_buttons_handler_context,
    create_mock_http_response
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
        self.app_config = Mock(spec=MattermostApplicationConfig)
        self.app_config.type = MessengerType.MATTERMOST
        self.app_config.address = "https://mattermost.example.com"
        self.app_config.team = "test-team"
        self.app_config.impulse_address = "https://impulse.example.com"
        self.app_config.chains = {}
        self.app_config.template_files = {}
        self.app_config.users = {}
        self.app_config.user_groups = {}
        self.app_config.groups = {}
        self.app_config.admin_users = []

        self.channels = {"default": {"id": "channel123"}}
        self.default_channel = "default"
    
    def _create_mattermost_app(self):
        """Helper to create MattermostApplication with groups initialized."""
        app = MattermostApplication(self.app_config, self.channels, self.default_channel)
        if not hasattr(app, 'groups'):
            app.groups = {}
        return app

    def test_mattermost_application_initialization(self):
        """Test MattermostApplication initialization."""
        app = self._create_mattermost_app()

        assert app.type == MessengerType.MATTERMOST
        assert app.url == "https://mattermost.example.com"
        assert app.team == "test-team"
        assert app.post_message_url == "https://mattermost.example.com/api/v4/posts"
        assert app.thread_id_key == "id"
        assert app.rate_limit is not None
        assert app.headers is not None
        assert "Authorization" in app.headers
        assert "Content-Type" in app.headers

    def test_get_url(self):
        """Test _get_url method."""
        app = self._create_mattermost_app()
        url = app._get_url(self.app_config)

        assert url == "https://mattermost.example.com"

    def test_get_public_url(self):
        """Test _get_public_url method."""
        app = self._create_mattermost_app()
        public_url = app._get_public_url(self.app_config)

        assert public_url == "https://mattermost.example.com"

    def test_get_team_name(self):
        """Test _get_team_name method."""
        app = self._create_mattermost_app()
        team_name = app._get_team_name(self.app_config)

        assert team_name == "test-team"

    def test_get_user_details_method_exists(self):
        """Test that get_user_details method exists and is callable."""
        app = self._create_mattermost_app()

        # Test that the method exists and is callable
        assert hasattr(app, 'get_user_details')
        assert callable(app.get_user_details)

    def test_get_user_details_parameters(self):
        """Test get_user_details method parameters."""
        app = self._create_mattermost_app()

        # Test that the method accepts the expected parameters
        import inspect
        sig = inspect.signature(app.get_user_details)
        params = list(sig.parameters.keys())

        assert 'user_details' in params

    def test_get_user_details_return_type(self):
        """Test get_user_details method return type annotation."""
        app = self._create_mattermost_app()

        # Test that the method is async
        import inspect
        assert inspect.iscoroutinefunction(app.get_user_details)

    def test_create_user(self):
        """Test create_user method."""
        app = self._create_mattermost_app()

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
        app = self._create_mattermost_app()

        # Mock admin users
        admin1 = Mock()
        admin1.username = "admin1"
        admin1.get_notification_identifier = Mock(return_value="admin1")
        admin2 = Mock()
        admin2.username = "admin2"
        admin2.get_notification_identifier = Mock(return_value="admin2")
        app.admin_users = [admin1, admin2]

        destinations = app.get_notification_destinations()

        assert destinations == ["admin1", "admin2"]

    def test_post_thread_payload(self):
        """Test _post_thread_payload method."""
        app = self._create_mattermost_app()

        result = app._post_thread_payload("channel123", "post123", "Test message")

        expected = {
            "channel_id": "channel123",
            "root_id": "post123",
            "message": "Test message"
        }
        assert result == expected

    def test_update_thread_method(self):
        """Test _update_thread method signature."""
        app = self._create_mattermost_app()

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
        app = self._create_mattermost_app()

        result = app._markdown_links_to_native_format("Test text with [link](url)")

        # Mattermost doesn't modify markdown links
        assert result == "Test text with [link](url)"

    @pytest.mark.asyncio
    async def test_buttons_handler_no_incident(self):
        """Test buttons_handler when no incident is found."""
        app = self._create_mattermost_app()

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
    async def test_update_thread_success(self):
        """Test _update_thread method with successful HTTP response."""
        app = self._create_mattermost_app()

        mock_response = create_mock_http_response()

        # Mock HTTP client
        app.http = Mock()
        app.http.put = AsyncMock(return_value=mock_response)

        await app._update_thread("post123", {"message": "Updated message"})

        app.http.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_group_details_success(self):
        """Test get_group_details method with successful API response."""
        app = self._create_mattermost_app()

        mock_response = create_mock_http_response(200)
        mock_response.json = AsyncMock(return_value={
            "id": "group123",
            "name": "Engineering Team",
            "display_name": "Engineering Team"
        })

        app.http = Mock()
        app.http.get = AsyncMock(return_value=mock_response)

        result = await app.get_group_details("group123")

        assert result == {
            "id": "group123",
            "name": "Engineering Team",
            "exists": True
        }

    @pytest.mark.asyncio
    async def test_get_group_details_not_found(self):
        """Test get_group_details method when group is not found."""
        app = self._create_mattermost_app()

        mock_response = create_mock_http_response(404)

        app.http = Mock()
        app.http.get = AsyncMock(return_value=mock_response)

        result = await app.get_group_details("group999")

        assert result == {
            "id": "group999",
            "name": None,
            "exists": False
        }

    @pytest.mark.asyncio
    async def test_get_group_details_http_error(self):
        """Test get_group_details method with HTTP error."""
        app = self._create_mattermost_app()

        mock_response = create_mock_http_response(500)

        app.http = Mock()
        app.http.get = AsyncMock(return_value=mock_response)

        result = await app.get_group_details("group123")

        assert result == {
            "id": "group123",
            "name": None,
            "exists": False
        }

    @pytest.mark.asyncio
    async def test_get_group_details_no_id(self):
        """Test get_group_details method with no group ID."""
        app = self._create_mattermost_app()

        result = await app.get_group_details(None)

        assert result == {
            "id": None,
            "name": None,
            "exists": False
        }

    @pytest.mark.asyncio
    async def test_generate_groups_success(self):
        """Test _generate_groups method with successful group validation."""
        app = self._create_mattermost_app()

        from app.config.validation import MattermostGroup
        groups_dict = {
            "eng": MattermostGroup(id="group123"),
            "ops": MattermostGroup(id="group456")
        }

        # Mock get_group_details
        async def mock_get_group_details(group_id):
            if group_id == "group123":
                return {"id": "group123", "name": "Engineering", "exists": True}
            elif group_id == "group456":
                return {"id": "group456", "name": "Operations", "exists": True}
            return {"id": group_id, "name": None, "exists": False}

        app.get_group_details = mock_get_group_details

        result = await app._generate_groups(groups_dict)

        assert len(result) == 2
        assert "eng" in result
        assert "ops" in result
        
        eng_group = result["eng"]
        assert eng_group.config_name == "eng"
        assert eng_group.name == "Engineering"
        assert eng_group.id == "group123"
        assert eng_group.exists is True

        ops_group = result["ops"]
        assert ops_group.config_name == "ops"
        assert ops_group.name == "Operations"
        assert ops_group.id == "group456"
        assert ops_group.exists is True

    @pytest.mark.asyncio
    async def test_generate_groups_not_found(self):
        """Test _generate_groups method when group is not found."""
        app = self._create_mattermost_app()

        from app.config.validation import MattermostGroup
        groups_dict = {
            "missing": MattermostGroup(id="group999")
        }

        app.get_group_details = AsyncMock(return_value={
            "id": "group999",
            "name": None,
            "exists": False
        })

        result = await app._generate_groups(groups_dict)

        assert len(result) == 1
        assert "missing" in result
        
        missing_group = result["missing"]
        assert missing_group.config_name == "missing"
        assert missing_group.name is None
        assert missing_group.id is None
        assert missing_group.exists is False

    @pytest.mark.asyncio
    async def test_generate_groups_no_id(self):
        """Test _generate_groups method when group has no ID."""
        app = self._create_mattermost_app()

        from app.config.validation import MattermostGroup
        # Use Mock instead of MattermostGroup since id is required in Pydantic model
        mock_group = Mock(spec=MattermostGroup)
        mock_group.id = None
        groups_dict = {
            "no_id": mock_group
        }

        result = await app._generate_groups(groups_dict)

        assert len(result) == 1
        assert "no_id" in result
        
        no_id_group = result["no_id"]
        assert no_id_group.config_name == "no_id"
        assert no_id_group.name is None
        assert no_id_group.id is None
        assert no_id_group.exists is False

    def test_create_group(self):
        """Test create_group method."""
        app = self._create_mattermost_app()

        group_details = {
            'id': 'group123',
            'name': 'Engineering Team',
            'exists': True
        }

        group = app.create_group("eng", group_details)

        assert group.config_name == "eng"
        assert group.name == "Engineering Team"
        assert group.id == "group123"
        assert group.exists is True

    def test_create_group_not_exists(self):
        """Test create_group method when group doesn't exist."""
        app = self._create_mattermost_app()

        group_details = {
            'id': None,
            'name': None,
            'exists': False
        }

        group = app.create_group("missing", group_details)

        assert group.config_name == "missing"
        assert group.name is None
        assert group.id is None
        assert group.exists is False
