"""
Test utility functions and mock helpers for the test suite.

This module provides reusable utilities for testing, particularly for mocking
aiohttp requests and other async operations.
"""
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, AsyncMock

# Constants for test configuration
DEFAULT_IMPULSE_ADDRESS = "https://impulse.example.com"


class MockContextManager:
    """
    A mock async context manager for testing aiohttp requests.
    
    This utility helps avoid code duplication when mocking aiohttp.ClientSession.post()
    calls that return async context managers.
    """

    def __init__(self, response):
        """
        Initialize the mock context manager with a response.
        
        Args:
            response: The mock response object to return when entering the context
        """
        self.response = response

    async def __aenter__(self):
        """Return the mock response when entering the context."""
        return self.response

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up when exiting the context."""
        pass


def create_mock_session_with_response(status_code=200):
    """
    Create a mock aiohttp session with a configured response.
    
    Args:
        status_code: HTTP status code for the mock response (default: 200)
        
    Returns:
        tuple: (mock_session, mock_response)
    """
    mock_response = AsyncMock()
    mock_response.status = status_code

    mock_session = AsyncMock()
    mock_session.post = Mock(return_value=MockContextManager(mock_response))

    return mock_session, mock_response


def create_mock_session_class_with_response(status_code=200):
    """
    Create a mock aiohttp.ClientSession class with a configured response.
    
    Args:
        status_code: HTTP status code for the mock response (default: 200)
        
    Returns:
        tuple: (mock_session_class, mock_session, mock_response)
    """
    mock_response = AsyncMock()
    mock_response.status = status_code

    mock_session = AsyncMock()
    mock_session.post = Mock(return_value=MockContextManager(mock_response))

    mock_session_class = Mock()
    mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)

    return mock_session_class, mock_session, mock_response


def setup_mock_session_class_patch(mock_session_class, status_code=200):
    """
    Setup a mock session class patch with a configured response.
    
    Args:
        mock_session_class: The mock session class from patch
        status_code: HTTP status code for the mock response (default: 200)
        
    Returns:
        tuple: (mock_session, mock_response)
    """
    mock_response = AsyncMock()
    mock_response.status = status_code

    mock_session = AsyncMock()
    mock_session.post = Mock(return_value=MockContextManager(mock_response))
    mock_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)

    return mock_session, mock_response


# ============================================================================
# Incident and Alert Test Utilities
# ============================================================================

def create_mock_chain(steps: List[Dict[str, Any]]) -> Mock:
    """
    Create a mock chain object with the specified steps.
    
    Args:
        steps: List of step dictionaries for the chain
        
    Returns:
        Mock chain object with steps attribute
    """
    mock_chain = Mock()
    mock_chain.steps = steps
    return mock_chain


def create_mock_chains_config(chain_configs: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Mock]:
    """
    Create a mock chains configuration dictionary.
    
    Args:
        chain_configs: Dictionary mapping chain names to their step lists
        
    Returns:
        Dictionary of mock chain objects
    """
    return {name: create_mock_chain(steps) for name, steps in chain_configs.items()}


def create_alert_payload(
        status: str = "firing",
        alertname: str = "TestAlert",
        service: str = "test-service",
        severity: str = "critical",
        instance: str = "test-instance",
        multiple_alerts: bool = False
) -> Dict[str, Any]:
    """
    Create a standardized alert payload for testing.
    
    Args:
        status: Alert status (firing, resolved, etc.)
        alertname: Name of the alert
        service: Service name
        severity: Alert severity
        instance: Instance name
        multiple_alerts: Whether to create multiple alerts
        
    Returns:
        Alert payload dictionary
    """
    base_alert = {
        "status": status,
        "labels": {
            "alertname": alertname,
            "service": service,
            "severity": severity,
            "instance": instance
        },
        "annotations": {
            "summary": f"{alertname} summary",
            "description": f"{alertname} description"
        },
        "startsAt": "2023-10-01T10:00:00Z",
        "endsAt": "0001-01-01T00:00:00Z" if status == "firing" else "2023-10-01T11:00:00Z",
        "generatorURL": f"https://prometheus:9090/graph?g0.expr=up%7Bjob%3D%22{service}%22%7D+%3D%3D+0&g0.tab=1"
    }

    alerts = [base_alert]
    if multiple_alerts:
        alerts.append({
            **base_alert,
            "labels": {**base_alert["labels"], "instance": "test-instance-2"},
            "status": "resolved" if status == "firing" else "firing"
        })

    return {
        "version": "4",
        "groupKey": f"{alertname}-{service}",
        "status": status,
        "receiver": "test-receiver",
        "groupLabels": {
            "alertname": alertname,
            "service": service
        },
        "commonLabels": {
            "alertname": alertname,
            "service": service,
            "severity": severity
        },
        "commonAnnotations": {
            "summary": f"{alertname} summary",
            "description": f"{alertname} description"
        },
        "externalURL": "https://alertmanager:9093",
        "alerts": alerts
    }


def create_firing_alerts_payload(
        alert_count: int = 2,
        base_alertname: str = "TestAlert"
) -> Dict[str, Any]:
    """
    Create an alert payload with multiple firing alerts for testing.
    
    Args:
        alert_count: Number of firing alerts to create
        base_alertname: Base name for alerts
        
    Returns:
        Alert payload with multiple firing alerts
    """
    alerts = []
    for i in range(alert_count):
        alerts.append({
            "status": "firing",
            "labels": {
                "alertname": f"{base_alertname}{i + 1}",
                "service": f"test-service-{i + 1}",
                "severity": "critical",
                "instance": f"test-instance-{i + 1}"
            },
            "annotations": {
                "summary": f"{base_alertname}{i + 1} summary",
                "description": f"{base_alertname}{i + 1} description"
            },
            "startsAt": "2023-10-01T10:00:00Z",
            "endsAt": "0001-01-01T00:00:00Z",
            "generatorURL":
                f"https://prometheus:9090/graph?g0.expr=up%7Bjob%3D%22test-service-{i + 1}%22%7D+%3D%3D+0&g0.tab=1"
        })

    return {
        "version": "4",
        "groupKey": f"{base_alertname}-group",
        "status": "firing",
        "receiver": "test-receiver",
        "groupLabels": {
            "alertname": base_alertname,
            "service": "test-service"
        },
        "commonLabels": {
            "alertname": base_alertname,
            "service": "test-service",
            "severity": "critical"
        },
        "commonAnnotations": {
            "summary": f"{base_alertname} summary",
            "description": f"{base_alertname} description"
        },
        "externalURL": "https://alertmanager:9093",
        "alerts": alerts
    }


def create_test_datetime(
        year: int = 2023,
        month: int = 10,
        day: int = 1,
        hour: int = 12,
        minute: int = 0,
        second: int = 0,
        tz: Optional[timezone] = None
) -> datetime:
    """
    Create a standardized test datetime.
    
    Args:
        year: Year
        month: Month
        day: Day
        hour: Hour
        minute: Minute
        second: Second
        tz: Timezone (defaults to UTC)
        
    Returns:
        Datetime object
    """
    return datetime(year, month, day, hour, minute, second, tzinfo=tz)


def create_mock_config(
        messenger_type: str = "slack",
        incidents_path: str = "/test/incidents",
        timeouts: Optional[Dict[str, str]] = None
) -> Mock:
    """
    Create a mock configuration object for testing.
    
    Args:
        messenger_type: Type of messenger (slack, mattermost, telegram)
        incidents_path: Path to incidents directory
        timeouts: Incident timeouts configuration
        
    Returns:
        Mock configuration object
    """
    if timeouts is None:
        timeouts = {"firing": "1h", "unknown": "30m", "resolved": "5m"}

    mock_config = Mock()
    mock_config.incidents_path = incidents_path
    mock_config.INCIDENT_ACTUAL_VERSION = "v3.0.0"

    # Mock incident config
    mock_incident_config = Mock()
    mock_incident_config.timeouts = timeouts
    mock_config.incident = mock_incident_config

    # Mock messenger config
    mock_messenger = Mock()
    mock_messenger.type.value = messenger_type
    mock_config.messenger = mock_messenger

    return mock_config


def create_mock_chain_step(
        step_type: str = "user",
        identifier: str = "testuser",
        has_chain: bool = False,
        chain_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a mock chain step for testing.
    
    Args:
        step_type: Type of step (user, wait, chain)
        identifier: Step identifier
        has_chain: Whether this step has a chain reference
        chain_name: Name of the chain if has_chain is True
        
    Returns:
        Chain step dictionary
    """
    step = {step_type: identifier}
    if has_chain and chain_name:
        step["chain"] = chain_name
    return step


def create_mock_chain_steps(
        steps_config: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Create a list of mock chain steps from configuration.
    
    Args:
        steps_config: List of step configurations
        
    Returns:
        List of chain step dictionaries
    """
    return [create_mock_chain_step(**config) for config in steps_config]


def create_mock_incident_data(
        status: str = "firing",
        channel_id: str = "C123456789",
        assigned_user_id: str = "U123456",
        assigned_user: str = "testuser",
        assigned_fullname: str = "Test User",
        messenger_type: str = "slack",
        ts: str = "1234567890.123456",
        link: str = "https://test.slack.comarchives/C123456789/p1234567890123456"
) -> Dict[str, Any]:
    """
    Create mock incident data for testing.
    
    Args:
        status: Incident status
        channel_id: Channel ID
        assigned_user_id: Assigned user ID
        assigned_user: Assigned user name
        assigned_fullname: Assigned user full name
        messenger_type: Messenger type
        ts: Timestamp
        link: Link to the incident
        
    Returns:
        Mock incident data dictionary
    """
    test_datetime = create_test_datetime()

    return {
        'version': 'v3.0.0',
        'status': status,
        'channel_id': channel_id,
        'payload': {'alertname': 'TestAlert', 'severity': 'critical'},
        'chain': [],
        'chain_enabled': False,
        'status_enabled': False,
        'status_update_datetime': test_datetime,
        'updated': test_datetime,
        'created': test_datetime,
        'assigned_user_id': assigned_user_id,
        'assigned_user': assigned_user,
        'assigned_fullname': assigned_fullname,
        'messenger_type': messenger_type,
        'ts': ts,
        'link': link
    }


def create_mock_event_loop(running: bool = True) -> Mock:
    """
    Create a mock event loop for testing.
    
    Args:
        running: Whether the event loop is running
        
    Returns:
        Mock event loop object
    """
    mock_loop = Mock()
    mock_loop.is_running.return_value = running
    return mock_loop


# ============================================================================
# Handler Test Utilities
# ============================================================================

def create_mock_queue() -> Mock:
    """
    Create a mock queue for testing handlers.
    
    Returns:
        Mock queue object with common async methods
    """
    queue = Mock()
    queue.put = AsyncMock()
    queue.recreate = AsyncMock()
    queue.update = AsyncMock()
    queue.delete_by_id = AsyncMock()
    return queue


def create_mock_application(
        messenger_type: str = "slack",
        url: str = "https://test.slack.com",
        team: str = "test-team",
        channels: Optional[Dict[str, Dict[str, str]]] = None,
        chains: Optional[Dict[str, Any]] = None,
        include_http_session: bool = False
) -> Mock:
    """
    Create a mock application for testing handlers.
    
    Args:
        messenger_type: Type of messenger (slack, mattermost, telegram)
        url: Application URL
        team: Team name
        channels: Dictionary of channel configurations
        chains: Dictionary of chain configurations
        include_http_session: Whether to include HTTP session
        
    Returns:
        Mock application object
    """
    if channels is None:
        channels = {'test-channel': {'id': 'C123456789'}}
    if chains is None:
        chains = {}

    app = Mock()
    app.type = Mock()
    app.type.value = messenger_type
    app.url = url
    app.team = team
    app.channels = channels
    app.chains = chains
    app.create_thread = AsyncMock(return_value='1234567890.123456')
    app.update = AsyncMock()
    app.post_thread = AsyncMock()
    app.format_text_italic = Mock(return_value='*formatted text*')
    app.get_notification_destinations = Mock(return_value=['admin1', 'admin2'])
    app.notify = AsyncMock(return_value=200)

    # Template mocks
    app.header_template = Mock()
    app.header_template.form_message = Mock(return_value='Header message')
    app.body_template = Mock()
    app.body_template.form_message = Mock(return_value='Body message')
    app.status_icons_template = Mock()
    app.status_icons_template.form_message = Mock(return_value='Status icons')

    app.public_url = url

    if include_http_session:
        app.http = Mock()

    return app


def create_mock_incidents_collection(
        by_uuid: Optional[Dict[str, Mock]] = None,
        include_get_method: bool = True
) -> Mock:
    """
    Create a mock incidents collection for testing handlers.
    
    Args:
        by_uuid: Dictionary of incidents by UUID
        include_get_method: Whether to include the get method
        
    Returns:
        Mock incidents collection object
    """
    if by_uuid is None:
        by_uuid = {}

    incidents = Mock()
    incidents.by_uuid = by_uuid
    incidents.del_by_uuid = Mock()

    if include_get_method:
        incidents.get = Mock(return_value=None)
        incidents.add = Mock()

    return incidents


def create_mock_route(
        channel_name: str = "test-channel",
        chain_name: str = "test-chain"
) -> Mock:
    """
    Create a mock route for testing handlers.
    
    Args:
        channel_name: Channel name to return
        chain_name: Chain name to return
        
    Returns:
        Mock route object
    """
    route = Mock()
    route.get_route.return_value = (channel_name, chain_name)
    return route


def create_mock_webhooks_collection() -> Mock:
    """
    Create a mock webhooks collection for testing handlers.
    
    Returns:
        Mock webhooks collection object
    """
    webhooks = Mock()
    webhooks.get.return_value = None
    return webhooks


def create_mock_incident_for_handlers(
        uuid: str = "test-uuid-123",
        status: str = "firing",
        channel_id: str = "C123456789",
        ts: str = "1234567890.123456",
        payload: Optional[Dict[str, Any]] = None,
        chain: Optional[List[Dict[str, Any]]] = None,
        chain_enabled: bool = True,
        status_enabled: bool = True,
        update_state_return: tuple = (True, True),
        set_next_status_return: bool = True
) -> Mock:
    """
    Create a mock incident for testing handlers.
    
    Args:
        uuid: Incident UUID
        status: Incident status
        channel_id: Channel ID
        ts: Timestamp
        payload: Incident payload
        chain: Incident chain
        chain_enabled: Whether chain is enabled
        status_enabled: Whether status updates are enabled
        update_state_return: Return value for update_state method
        set_next_status_return: Return value for set_next_status method
        
    Returns:
        Mock incident object
    """
    if payload is None:
        payload = {'alertname': 'TestAlert'}
    if chain is None:
        chain = []

    incident = Mock()
    incident.uuid = uuid
    incident.status = status
    incident.channel_id = channel_id
    incident.ts = ts
    incident.payload = payload
    incident.chain = chain
    incident.chain_enabled = chain_enabled
    incident.status_enabled = status_enabled
    incident.status_update_datetime = create_test_datetime()
    incident.set_next_status = Mock(return_value=set_next_status_return)
    incident.update_state = Mock(return_value=update_state_return)
    incident.is_new_firing_alerts_added = Mock(return_value=False)
    incident.is_some_firing_alerts_removed = Mock(return_value=False)
    incident.get_chain = Mock(return_value=chain)
    incident.chain_update = Mock()
    incident.dump = Mock()
    incident.generate_chain = Mock()
    incident.link = f'https://test.slack.com/archives/{channel_id}/p{ts}'

    return incident


def create_mock_webhook(
        name: str = "test-webhook",
        push_result: str = "ok",
        response_code: int = 200
) -> Mock:
    """
    Create a mock webhook for testing handlers.
    
    Args:
        name: Webhook name
        push_result: Result from push method
        response_code: HTTP response code
        
    Returns:
        Mock webhook object
    """
    webhook = Mock()
    webhook.name = name
    webhook.push = AsyncMock(return_value=(push_result, response_code))
    return webhook


# ============================================================================
# Configuration Test Utilities
# ============================================================================

def create_mock_impulse_config(
        messenger_type: str = "slack",
        channels: Optional[Dict[str, Dict[str, str]]] = None,
        users: Optional[Dict[str, Dict[str, str]]] = None,
        admin_users: Optional[List[str]] = None,
        incident_config: Optional[Dict[str, Any]] = None,
        ui_config: Optional[Dict[str, Any]] = None
) -> Mock:
    """
    Create a mock ImpulseConfig for testing.
    
    Args:
        messenger_type: Type of messenger (slack, mattermost, telegram)
        channels: Dictionary of channel configurations
        users: Dictionary of user configurations
        admin_users: List of admin users
        incident_config: Incident configuration dictionary
        ui_config: UI configuration dictionary
        
    Returns:
        Mock ImpulseConfig object
    """
    if channels is None:
        channels = {"default": {"id": "C123456789"}}
    if users is None:
        users = {"admin1": {"id": "U123456"}}
    if admin_users is None:
        admin_users = ["admin1", "admin2"]
    if incident_config is None:
        incident_config = {"timeouts": {"firing": "1h", "unknown": "30m", "resolved": "5m"}}
    if ui_config is None:
        ui_config = {"columns": [{"name": "status", "header": "Status", "value": "status"}]}

    config = Mock()
    config.messenger = Mock()
    config.messenger.type = Mock()
    config.messenger.type.value = messenger_type
    config.messenger.channels = channels
    config.messenger.users = users
    config.messenger.admin_users = admin_users
    config.messenger.chains = {}
    config.messenger.template_files = Mock()
    config.messenger.template_files.status_icons = None
    config.messenger.template_files.header = None
    config.messenger.template_files.body = None

    config.incident = Mock()
    config.incident.timeouts = incident_config.get("timeouts", {})
    config.incident.notifications = incident_config.get("notifications", {})

    config.ui = ui_config
    config.webhooks = {}

    return config


def create_mock_environment_config(**overrides) -> Mock:
    """
    Create a mock EnvironmentConfig for testing.
    
    This function creates a mock EnvironmentConfig with sensible defaults.
    You can override any attribute by passing it as a keyword argument.
    
    Args:
        **overrides: Any EnvironmentConfig attributes to override from defaults
        
    Common overrides:
        slack_bot_token: Slack bot user OAuth token (default: "test-slack-token")
        slack_verification_token: Slack verification token (default: "test-verification-token")
        mattermost_token: Mattermost access token (default: "test-mattermost-token")
        telegram_token: Telegram bot token (default: "test-telegram-token")
        data_path: Data directory path (default: "test_data")
        config_path: Configuration file path (default: "test_config.yml")
        incidents_path: Incidents directory path (default: "test_data/incidents")
        provider_sync_interval: Provider sync interval (default: 300)
        provider_max_events: Maximum events to sync (default: 100)
        provider_days_to_sync: Days to sync (default: 7)
        service_account_file: Service account file path (default: "test_service_account.json")
        cors_origins: CORS allowed origins (default: ["*"])
        http_prefix: HTTP prefix (default: "")
        log_level: Log level (default: "INFO")
        listen_host: Listen host (default: "0.0.0.0")
        listen_port: Listen port (default: 5000)
        
    Returns:
        Mock EnvironmentConfig object
        
    Examples:
        >>> config = create_mock_environment_config()
        >>> config = create_mock_environment_config(log_level="DEBUG")
        >>> config = create_mock_environment_config(data_path="/custom/data", log_level="DEBUG")
    """
    # Default values
    defaults = {
        "slack_bot_user_oauth_token": "test-slack-token",
        "slack_verification_token": "test-verification-token",
        "mattermost_access_token": "test-mattermost-token",
        "telegram_bot_token": "test-telegram-token",
        "data_path": "test_data",
        "config_path": "test_config.yml",
        "incidents_path": "test_data/incidents",
        "provider_sync_interval": 300,
        "provider_max_events": 100,
        "provider_days_to_sync": 7,
        "provider_service_account_file": "test_service_account.json",
        "cors_allowed_origins": ["*"],
        "http_prefix": "",
        "log_level": "INFO",
        "listen_host": "0.0.0.0",
        "listen_port": 5000
    }
    
    # Handle parameter name mapping for backwards compatibility
    param_mapping = {
        "slack_bot_token": "slack_bot_user_oauth_token",
        "mattermost_token": "mattermost_access_token",
        "telegram_token": "telegram_bot_token",
        "service_account_file": "provider_service_account_file",
        "cors_origins": "cors_allowed_origins"
    }
    
    # Apply parameter name mapping
    for old_name, new_name in param_mapping.items():
        if old_name in overrides:
            overrides[new_name] = overrides.pop(old_name)
    
    # Merge overrides with defaults
    config_values = {**defaults, **overrides}
    
    # Create mock object with all attributes
    env_config = Mock()
    for key, value in config_values.items():
        setattr(env_config, key, value)

    return env_config


def create_slack_config_data(
        admin_users: Optional[List[str]] = None,
        channels: Optional[Dict[str, Dict[str, str]]] = None,
        users: Optional[Dict[str, Dict[str, str]]] = None,
        chains: Optional[Dict[str, Any]] = None,
        ui_columns: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """
    Create a standardized Slack configuration data for testing.
    
    Args:
        admin_users: List of admin users
        channels: Dictionary of channel configurations
        users: Dictionary of user configurations
        chains: Dictionary of chain configurations
        ui_columns: List of UI column configurations
        
    Returns:
        Slack configuration data dictionary
    """
    if admin_users is None:
        admin_users = ["admin1", "admin2"]
    if channels is None:
        channels = {"default": {"id": "C123456789"}}
    if users is None:
        users = {"admin1": {"id": "U123456"}}
    if chains is None:
        chains = {}
    if ui_columns is None:
        ui_columns = [{"name": "status", "header": "Status", "value": "status"}]

    return {
        "messenger": {
            "type": "slack",
            "admin_users": admin_users,
            "channels": channels,
            "users": users,
            "template_files": {},
            "chains": chains
        },
        "route": {
            "channel": "default",
            "chain": "test_chain",
            "routes": [],
            "matchers": []
        },
        "ui": {
            "columns": ui_columns
        }
    }


def create_mattermost_config_data(
        admin_users: Optional[List[str]] = None,
        channels: Optional[Dict[str, Dict[str, str]]] = None,
        users: Optional[Dict[str, Dict[str, str]]] = None,
        address: str = "https://mattermost.example.com",
        team: str = "test-team",
        impulse_address: str = DEFAULT_IMPULSE_ADDRESS
) -> Dict[str, Any]:
    """
    Create a standardized Mattermost configuration data for testing.
    
    Args:
        admin_users: List of admin users
        channels: Dictionary of channel configurations
        users: Dictionary of user configurations
        address: Mattermost server address
        team: Mattermost team name
        impulse_address: Impulse callback address
        
    Returns:
        Mattermost configuration data dictionary
    """
    if admin_users is None:
        admin_users = ["admin1"]
    if channels is None:
        channels = {"default": {"id": "channel123"}}
    if users is None:
        users = {"admin1": {"id": "user123"}}

    return {
        "messenger": {
            "type": "mattermost",
            "admin_users": admin_users,
            "channels": channels,
            "users": users,
            "template_files": {},
            "address": address,
            "team": team,
            "impulse_address": impulse_address
        },
        "route": {
            "channel": "default",
            "chain": "test_chain",
            "routes": [],
            "matchers": []
        },
        "ui": {
            "columns": [{"name": "status", "header": "Status", "value": "status"}]
        }
    }


def create_telegram_config_data(
        admin_users: Optional[List[str]] = None,
        channels: Optional[Dict[str, Dict[str, int]]] = None,
        users: Optional[Dict[str, Dict[str, int]]] = None,
        impulse_address: str = DEFAULT_IMPULSE_ADDRESS
) -> Dict[str, Any]:
    """
    Create a standardized Telegram configuration data for testing.
    
    Args:
        admin_users: List of admin users
        channels: Dictionary of channel configurations
        users: Dictionary of user configurations
        impulse_address: Impulse callback address
        
    Returns:
        Telegram configuration data dictionary
    """
    if admin_users is None:
        admin_users = ["admin1"]
    if channels is None:
        channels = {"default": {"id": -1001234567890}}
    if users is None:
        users = {"admin1": {"id": 123456789}}

    return {
        "messenger": {
            "type": "telegram",
            "admin_users": admin_users,
            "channels": channels,
            "users": users,
            "template_files": {},
            "impulse_address": impulse_address
        },
        "route": {
            "channel": "default",
            "chain": "test_chain",
            "routes": [],
            "matchers": []
        },
        "ui": {
            "columns": [{"name": "status", "header": "Status", "value": "status"}]
        }
    }


def create_incident_config_data(
        notifications: Optional[Dict[str, bool]] = None,
        timeouts: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Create a standardized incident configuration data for testing.
    
    Args:
        notifications: Incident notification settings
        timeouts: Incident timeout settings
        
    Returns:
        Incident configuration data dictionary
    """
    if notifications is None:
        notifications = {
            "assignment": True,
            "new_firing": True,
            "partial_resolved": False
        }
    if timeouts is None:
        timeouts = {
            "firing": "6h",
            "unknown": "1h",
            "resolved": "5m"
        }

    return {
        "notifications": notifications,
        "timeouts": timeouts
    }


def create_webhook_config_data(
        name: str = "test_webhook",
        url: str = "https://example.com/webhook",
        data: Optional[Dict[str, Any]] = None,
        json_payload: Optional[Dict[str, Any]] = None,
        auth: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a standardized webhook configuration data for testing.
    
    Args:
        name: Webhook name
        url: Webhook URL
        data: Webhook data payload
        json_payload: Webhook JSON payload
        auth: HTTP Basic Auth
        
    Returns:
        Webhook configuration data dictionary
    """
    if data is None:
        data = {"message": "test"}
    if json_payload is None:
        json_payload = None
    if auth is None:
        auth = "user:pass"

    webhook_config = {
        "url": url,
        "auth": auth
    }

    if json_payload is not None:
        webhook_config["json"] = json_payload
    else:
        webhook_config["data"] = data

    return webhook_config


def create_ui_config_data(
        columns: Optional[List[Dict[str, str]]] = None,
        colors: Optional[Dict[str, Dict[str, str]]] = None,
        filters: Optional[List[str]] = None,
        sorting: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """
    Create a standardized UI configuration data for testing.
    
    Args:
        columns: List of UI column configurations
        colors: Color configurations
        filters: Default filters
        sorting: Sort rules
        
    Returns:
        UI configuration data dictionary
    """
    if columns is None:
        columns = [
            {"name": "status", "header": "Status", "value": "status"},
            {"name": "created", "header": "Created", "value": "created", "type": "datetime"}
        ]
    if colors is None:
        colors = {}
    if filters is None:
        filters = []
    if sorting is None:
        sorting = []

    return {
        "columns": columns,
        "colors": colors,
        "filters": filters,
        "sorting": sorting
    }


# ============================================================================
# Async Task Test Utilities
# ============================================================================

class MockAsyncTask:
    """
    A mock asyncio.Task that can be awaited and behaves like a real task.
    
    This utility helps avoid RuntimeWarnings about coroutines not being awaited
    when testing async queue managers and other async components.
    """

    def __init__(self, cancelled: bool = False):
        """
        Initialize the mock task.
        
        Args:
            cancelled: Whether the task is initially cancelled
        """
        self._cancelled = cancelled
        # Ensure no coroutines are created during initialization
        self._done = False
        self._result = None
        self._exception = None

    def cancel(self):
        """Cancel the task."""
        self._cancelled = True
        # Don't create any coroutines here

    def cancelled(self):
        """Check if the task is cancelled."""
        return self._cancelled

    def done(self):
        """Check if the task is done."""
        return self._done or self._cancelled

    def result(self):
        """Get the task result."""
        return self._result

    def exception(self):
        """Get the task exception."""
        return self._exception

    def __await__(self):
        """Make the task awaitable by returning an empty iterator."""
        return iter([])

    def __repr__(self):
        """String representation."""
        return f"MockAsyncTask(cancelled={self._cancelled})"


def create_mock_async_task(cancelled: bool = False) -> MockAsyncTask:
    """
    Create a mock asyncio.Task for testing.
    
    Args:
        cancelled: Whether the task should be initially cancelled
        
    Returns:
        MockAsyncTask object that behaves like a real asyncio.Task
    """
    return MockAsyncTask(cancelled=cancelled)


# ============================================================================
# Configuration Mocking Utilities
# ============================================================================

def create_mock_get_config_patch(impulse_address: str = DEFAULT_IMPULSE_ADDRESS):
    """
    Create a mock for get_config() that returns a config with impulse_address.
    
    This utility helps avoid AttributeError when testing applications that call
    get_config() internally and expect impulse_address to be available.
    
    Args:
        impulse_address: The impulse address to set in the mock config
        
    Returns:
        Mock object that can be used with patch
    """
    # Create a mock that mimics the UnifiedConfig structure
    mock_config = Mock()
    
    # Create a mock app config (ImpulseConfig)
    mock_app = Mock()
    
    # Create a mock messenger config with impulse_address (MattermostApplicationConfig)
    mock_messenger = Mock()
    mock_messenger.impulse_address = impulse_address
    mock_messenger.type = Mock()
    mock_messenger.type.value = "mattermost"
    
    # Set up the messenger property to return our mock
    mock_app.messenger = mock_messenger
    mock_config.app = mock_app
    mock_config.messenger = mock_messenger  # Direct access for convenience
    
    return Mock(return_value=mock_config)


# ============================================================================
# Application Test Utilities (Shared)
# ============================================================================

def setup_app_templates(app):
    """
    Setup mock templates for any application tests.
    
    Args:
        app: The application instance
    """
    app.body_template = Mock()
    app.body_template.form_message.return_value = "Test body"
    app.header_template = Mock()
    app.header_template.form_message.return_value = "Test header"
    app.status_icons_template = Mock()
    app.status_icons_template.form_message.return_value = "Test icons"


def convert_mock_to_async_if_needed(patch_name: str, patch_value):
    """
    Convert Mock to AsyncMock if needed for async methods.
    
    Args:
        patch_name: Name of the patch
        patch_value: The patch value
        
    Returns:
        Converted patch value
    """
    async_methods = ['post_assignment_notification', 'post_unassignment_notification', 'fetch_and_assign_user_name']
    if patch_name in async_methods and not hasattr(patch_value, '__await__'):
        from unittest.mock import AsyncMock
        return AsyncMock()
    return patch_value


def _prepare_button_handler_patches(app, additional_patches, app_specific_patches):
    """
    Prepare all patches and patch objects for button handler tests.
    
    Args:
        app: The application instance
        additional_patches: Additional patches to apply
        app_specific_patches: List of app-specific patches to apply
        
    Returns:
        Tuple of (patches_context, patch_objects)
    """
    from unittest.mock import patch
    
    patch_objects = {}
    patches_context = []
    
    # Process additional patches
    if additional_patches:
        for patch_name, patch_value in additional_patches.items():
            patch_value = convert_mock_to_async_if_needed(patch_name, patch_value)
            patch_objects[patch_name] = patch_value
            patches_context.append(patch.object(app, patch_name, patch_value))
    
    # Add app-specific patches
    if app_specific_patches:
        patches_context.extend(app_specific_patches)
    
    return patches_context, patch_objects


def _find_logger_mock_in_patches(patches_context):
    """
    Find the logger mock from patches.
    
    Args:
        patches_context: List of patch contexts
        
    Returns:
        Logger mock if found, None otherwise
    """
    for patch_context in patches_context:
        if hasattr(patch_context, 'new') and 'logger' in str(patch_context):
            return patch_context.new
    return None


def _apply_all_patches(patches_context):
    """
    Start all patches.
    
    Args:
        patches_context: List of patch contexts to start
    """
    for patch_context in patches_context:
        patch_context.start()


def _cleanup_all_patches(patches_context):
    """
    Stop all patches.
    
    Args:
        patches_context: List of patch contexts to stop
    """
    for patch_context in patches_context:
        patch_context.stop()


def create_buttons_handler_context_manager(app, payload, incidents, queue, route,
                                         expected_log_message: str = None,
                                         additional_patches: dict = None,
                                         app_specific_setup=None,
                                         app_specific_patches=None):
    """
    Create a generic context manager for testing buttons_handler with common setup.
    
    Args:
        app: The application instance
        payload: The payload
        incidents: Mock incidents collection
        queue: Mock queue
        route: Mock route
        expected_log_message: Expected log message for assertion
        additional_patches: Additional patches to apply
        app_specific_setup: Function to call for app-specific setup
        app_specific_patches: List of app-specific patches to apply
        
    Returns:
        Context manager that yields (result, mock_logger, patch_objects)
    """
    from contextlib import asynccontextmanager
    from fastapi.responses import JSONResponse
    
    @asynccontextmanager
    async def test_context():
        # Prepare patches
        patches_context, patch_objects = _prepare_button_handler_patches(
            app, additional_patches, app_specific_patches
        )
        
        # Call app-specific setup
        if app_specific_setup:
            app_specific_setup(app)
        
        # Apply all patches
        _apply_all_patches(patches_context)
        
        try:
            # Execute the handler
            result = await app.buttons_handler(payload, incidents, queue, route)
            
            # Common assertions
            assert isinstance(result, JSONResponse)
            assert result.status_code == 200
            
            # Log message assertion
            mock_logger = None
            if expected_log_message and patches_context:
                mock_logger = _find_logger_mock_in_patches(patches_context)
                if mock_logger:
                    mock_logger.info.assert_called_with(expected_log_message)
            
            yield result, mock_logger, patch_objects
        finally:
            # Cleanup all patches
            _cleanup_all_patches(patches_context)
    
    return test_context()


# ============================================================================
# Slack Application Test Utilities
# ============================================================================

def create_slack_mock_config(token: str = "valid_token"):
    """
    Create a mock config for Slack application tests.
    
    Args:
        token: The Slack verification token
        
    Returns:
        Mock config object
    """
    mock_config = Mock()
    mock_config.slack_verification_token = token
    return mock_config


def create_slack_buttons_handler_context(app, payload, incidents, queue, route, 
                                        expected_log_message: str = None,
                                        additional_patches: dict = None):
    """
    Create a context manager for testing Slack buttons_handler with common setup.
    
    Args:
        app: The Slack application instance
        payload: The Slack payload
        incidents: Mock incidents collection
        queue: Mock queue
        route: Mock route
        expected_log_message: Expected log message for assertion
        additional_patches: Additional patches to apply
        
    Returns:
        Context manager that yields (result, mock_logger, mock_reformat, patch_objects)
    """
    from contextlib import asynccontextmanager
    from unittest.mock import patch
    
    @asynccontextmanager
    async def slack_context():
        with patch('app.im.slack.slack_application.get_config') as mock_get_config:
            mock_config = create_slack_mock_config()
            mock_get_config.return_value = mock_config
            
            with patch('app.im.slack.slack_application.logger') as mock_logger:
                with patch('app.im.slack.slack_application.reformat_message') as mock_reformat:
                    mock_reformat.return_value = {"text": "Modified message"}
                    
                    async with create_buttons_handler_context_manager(
                        app, payload, incidents, queue, route,
                        expected_log_message=expected_log_message,
                        additional_patches=additional_patches,
                        app_specific_setup=lambda app: setup_app_templates(app)
                    ) as (result, _, patch_objects):
                        yield result, mock_logger, mock_reformat, patch_objects
    
    return slack_context()


# ============================================================================
# Mattermost Application Test Utilities
# ============================================================================

def create_mattermost_buttons_handler_context(app, payload, incidents, queue, route, 
                                             expected_log_message: str = None,
                                             additional_patches: dict = None,
                                             patch_get_config: bool = True):
    """
    Create a context manager for testing Mattermost buttons_handler with common setup.
    
    Args:
        app: The Mattermost application instance
        payload: The Mattermost payload
        incidents: Mock incidents collection
        queue: Mock queue
        route: Mock route
        expected_log_message: Expected log message for assertion
        additional_patches: Additional patches to apply
        patch_get_config: Whether to patch get_config (default: True)
        
    Returns:
        Context manager that yields (result, mock_logger, patch_objects)
    """
    from contextlib import asynccontextmanager
    from unittest.mock import patch
    
    @asynccontextmanager
    async def mattermost_context():
        with patch('app.im.mattermost.mattermost_application.logger') as mock_logger:
            # Always patch threads.get_config since it's called by mattermost_get_button_update_payload
            with patch('app.im.mattermost.threads.get_config', create_mock_get_config_patch()):
                if patch_get_config:
                    # Also patch the main get_config for other uses
                    with patch('app.config.config.get_config', create_mock_get_config_patch()):
                        async with create_buttons_handler_context_manager(
                            app, payload, incidents, queue, route,
                            expected_log_message=expected_log_message,
                            additional_patches=additional_patches,
                            app_specific_setup=lambda app: setup_app_templates(app)
                        ) as (result, _, patch_objects):
                            yield result, mock_logger, patch_objects
                else:
                    async with create_buttons_handler_context_manager(
                        app, payload, incidents, queue, route,
                        expected_log_message=expected_log_message,
                        additional_patches=additional_patches,
                        app_specific_setup=lambda app: setup_app_templates(app)
                    ) as (result, _, patch_objects):
                        yield result, mock_logger, patch_objects
    
    return mattermost_context()


# ============================================================================
# Telegram Application Test Utilities
# ============================================================================

def create_telegram_buttons_handler_context(app, payload, incidents, queue, route, 
                                           expected_log_message: str = None,
                                           additional_patches: dict = None):
    """
    Create a context manager for testing Telegram buttons_handler with common setup.
    
    Args:
        app: The Telegram application instance
        payload: The Telegram payload
        incidents: Mock incidents collection
        queue: Mock queue
        route: Mock route
        expected_log_message: Expected log message for assertion
        additional_patches: Additional patches to apply
        
    Returns:
        Context manager that yields (result, mock_logger, patch_objects)
    """
    from contextlib import asynccontextmanager
    from unittest.mock import patch, AsyncMock
    
    @asynccontextmanager
    async def telegram_context():
        with patch('app.im.telegram.telegram_application.logger') as mock_logger:
            # Always patch update_thread and http.post for Telegram
            with patch.object(app, 'update_thread'):
                with patch.object(app.http, 'post', new_callable=AsyncMock):
                    async with create_buttons_handler_context_manager(
                        app, payload, incidents, queue, route,
                        expected_log_message=expected_log_message,
                        additional_patches=additional_patches,
                        app_specific_setup=lambda app: setup_app_templates(app)
                    ) as (result, _, patch_objects):
                        yield result, mock_logger, patch_objects
    
    return telegram_context()
