"""
Pytest configuration and fixtures for the IMPulse application test suite.
"""
import asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from app.config.config import UnifiedConfig
from app.config.environment import EnvironmentConfig
from app.config.validation import ImpulseConfig, SlackApplicationConfig, MattermostApplicationConfig, MessengerType
from app.incident.incident import Incident, IncidentConfig


@pytest.fixture(autouse=True, scope="session")
def mock_get_config_globally():
    """
    Global fixture to mock get_config() for all tests.
    This ensures tests don't depend on actual config files.
    """
    def create_mock_config_for_app(app_type="mattermost"):
        """Create a mock config that matches the expected application type."""
        # Create environment config
        env_config = Mock(spec=EnvironmentConfig)
        env_config.slack_bot_user_oauth_token = "test-slack-token"
        env_config.slack_verification_token = "test-verification-token"
        env_config.mattermost_access_token = "test-mattermost-token"
        env_config.telegram_bot_token = "test-telegram-token"
        env_config.data_path = "test_data"
        env_config.config_path = "test_config.yml"
        env_config.incidents_path = "test_data/incidents"
        env_config.provider_sync_interval = 300
        env_config.provider_max_events = 100
        env_config.provider_days_to_sync = 7
        env_config.provider_service_account_file = "test_service_account.json"
        env_config.cors_allowed_origins = ["*"]
        env_config.http_prefix = ""
        
        # Create app config
        app_config = Mock(spec=ImpulseConfig)
        
        # Create messenger config based on app type
        if app_type == "mattermost":
            messenger = Mock(spec=MattermostApplicationConfig)
            messenger.type = MessengerType.MATTERMOST
            messenger.impulse_address = "https://impulse.example.com"
            messenger.address = "https://mattermost.example.com"
            messenger.team = "test-team"
            messenger.channels = {"default": {"id": "C123456789"}}
            messenger.users = {}
            messenger.admin_users = []
            messenger.chains = {}
            messenger.template_files = Mock()
        elif app_type == "slack":
            messenger = Mock(spec=SlackApplicationConfig)
            messenger.type = MessengerType.SLACK
            messenger.channels = {"default": {"id": "C123456789"}}
            messenger.users = {}
            messenger.admin_users = []
            messenger.chains = {}
            messenger.template_files = Mock()
        else:  # telegram or default
            messenger = Mock()
            messenger.type = Mock()
            messenger.type.value = app_type
            messenger.impulse_address = "https://impulse.example.com"
            messenger.channels = {"default": {"id": "C123456789"}}
            messenger.users = {}
            messenger.admin_users = []
            messenger.chains = {}
            messenger.template_files = Mock()
        
        app_config.messenger = messenger
        
        # Create other configs
        app_config.incident = Mock()
        app_config.incident.timeouts = {"firing": "1h", "unknown": "30m", "resolved": "5m"}
        app_config.ui = Mock()
        app_config.ui.columns = []
        
        # Create unified config
        unified_config = Mock(spec=UnifiedConfig)
        unified_config.env = env_config
        unified_config.app = app_config
        unified_config.INCIDENT_ACTUAL_VERSION = "v3.0.0"
        unified_config.check_updates = True
        unified_config.messenger = messenger
        unified_config.incident = app_config.incident
        unified_config.ui_config = app_config.ui
        unified_config.incidents_path = env_config.incidents_path
        unified_config.http_prefix = env_config.http_prefix
        
        return unified_config
    
    # Create a mock that returns the appropriate config based on context
    def mock_get_config():
        # Try to determine the app type from the calling context
        import inspect
        frame = inspect.currentframe()
        try:
            # Look at the calling frame to determine app type
            calling_frame = frame.f_back
            if calling_frame:
                filename = calling_frame.f_code.co_filename
                if 'mattermost' in filename:
                    return create_mock_config_for_app("mattermost")
                elif 'slack' in filename:
                    return create_mock_config_for_app("slack")
                elif 'telegram' in filename:
                    return create_mock_config_for_app("telegram")
        finally:
            del frame
        
        # Default to mattermost for most cases
        return create_mock_config_for_app("mattermost")
    
    # Also patch the config loading functions to prevent file I/O
    def mock_load_unified_config(config_path=None, exit_on_error=True):
        return create_mock_config_for_app("mattermost")
    
    def mock_validate_config(data):
        return create_mock_config_for_app("mattermost")
    
    def mock_load_and_validate_config(config_path=None):
        config = create_mock_config_for_app("mattermost")
        return config, {}
    
    with patch('app.config.config.get_config', side_effect=mock_get_config), \
         patch('app.config.config.load_unified_config', side_effect=mock_load_unified_config), \
         patch('app.config.validation.validate_config', side_effect=mock_validate_config), \
         patch('app.config.loader.load_and_validate_config', side_effect=mock_load_and_validate_config):
        yield


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_environment_config():
    """Mock environment configuration for testing."""
    env_config = Mock(spec=EnvironmentConfig)
    env_config.slack_bot_user_oauth_token = "test-slack-token"
    env_config.slack_verification_token = "test-verification-token"
    env_config.mattermost_access_token = "test-mattermost-token"
    env_config.telegram_bot_token = "test-telegram-token"
    env_config.data_path = "test_data"
    env_config.config_path = "test_config.yml"
    env_config.incidents_path = "test_data/incidents"
    env_config.provider_sync_interval = 300
    env_config.provider_max_events = 100
    env_config.provider_days_to_sync = 7
    env_config.provider_service_account_file = "test_service_account.json"
    env_config.cors_allowed_origins = ["*"]
    env_config.http_prefix = ""
    return env_config


@pytest.fixture
def mock_impulse_config():
    """Mock ImpulseConfig for testing."""
    config = Mock(spec=ImpulseConfig)

    # Mock messenger config
    messenger = Mock(spec=SlackApplicationConfig)
    messenger.type = MessengerType.SLACK
    messenger.channels = {"default": {"id": "C123456789"}}
    messenger.users = {}
    messenger.route = True
    messenger.webhooks = Mock()
    config.messenger = messenger

    # Mock other configs
    config.incident = Mock()
    config.incident.timeouts = {"firing": "1h", "unknown": "30m", "resolved": "5m"}
    config.ui = True

    return config


@pytest.fixture
def mock_unified_config(mock_environment_config, mock_impulse_config):
    """Mock UnifiedConfig for testing."""
    config = Mock(spec=UnifiedConfig)
    config.env = mock_environment_config
    config.app = mock_impulse_config
    config.INCIDENT_ACTUAL_VERSION = "v3.0.0"
    config.check_updates = True
    config.messenger = mock_impulse_config.messenger
    config.incident = mock_impulse_config.incident
    config.ui_config = mock_impulse_config.ui
    config.incidents_path = mock_environment_config.incidents_path
    config.http_prefix = mock_environment_config.http_prefix
    return config


@pytest.fixture
def sample_alert_payload():
    """Sample alert payload for testing incidents."""
    return {
        "version": "4",
        "groupKey": "test-group",
        "status": "firing",
        "receiver": "test-receiver",
        "groupLabels": {
            "alertname": "TestAlert",
            "service": "test-service"
        },
        "commonLabels": {
            "alertname": "TestAlert",
            "service": "test-service",
            "severity": "critical"
        },
        "commonAnnotations": {
            "summary": "Test alert summary",
            "description": "Test alert description"
        },
        "externalURL": "https://alertmanager:9093",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "TestAlert",
                    "service": "test-service",
                    "severity": "critical",
                    "instance": "test-instance"
                },
                "annotations": {
                    "summary": "Test alert summary",
                    "description": "Test alert description"
                },
                "startsAt": "2023-10-01T10:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "https://prometheus:9090/graph?g0.expr=up%7Bjob%3D%22test-service%22%7D+%3D%3D+0&g0.tab=1"
            }
        ]
    }


@pytest.fixture
def incident_config():
    """Sample incident configuration for testing."""
    return IncidentConfig(
        application_type="slack",
        application_url="https://test.slack.com",
        application_team="test-team"
    )


@pytest.fixture
def sample_incident(sample_alert_payload, incident_config):
    """Sample incident for testing."""
    return Incident(
        payload=sample_alert_payload,
        status="firing",
        channel_id="C123456789",
        config=incident_config,
        status_update_datetime=datetime.now(timezone.utc),
        assigned_user_id="",
        assigned_user="",
        assigned_fullname="",
        messenger_type="slack"
    )


@pytest.fixture
def mock_datetime():
    """Mock datetime for consistent testing."""
    fixed_time = datetime(2023, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
    with pytest.mock.patch('app.incident.incident.datetime') as mock_dt:
        mock_dt.now.return_value = fixed_time
        mock_dt.utcnow.return_value = fixed_time.replace(tzinfo=None)
        yield mock_dt


@pytest.fixture
def mock_file_operations():
    """Mock file operations for testing."""
    with pytest.mock.patch('builtins.open'), \
            pytest.mock.patch('yaml.dump'), \
            pytest.mock.patch('yaml.load'):
        yield
