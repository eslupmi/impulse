"""
Pytest configuration and fixtures for the IMPulse application test suite.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone
from typing import Dict, Any

from app.config.config import UnifiedConfig
from app.config.environment import EnvironmentConfig
from app.config.validation import ImpulseConfig, SlackApplicationConfig, MessengerType
from app.incident.incident import Incident, IncidentConfig


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


