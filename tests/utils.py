"""
Test utility functions and mock helpers for the test suite.

This module provides reusable utilities for testing, particularly for mocking
aiohttp requests and other async operations.
"""
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, AsyncMock


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
        "generatorURL": f"http://prometheus:9090/graph?g0.expr=up%7Bjob%3D%22{service}%22%7D+%3D%3D+0&g0.tab=1"
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
        "externalURL": "http://alertmanager:9093",
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
            "generatorURL": f"http://prometheus:9090/graph?g0.expr=up%7Bjob%3D%22test-service-{i + 1}%22%7D+%3D%3D+0&g0.tab=1"
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
        "externalURL": "http://alertmanager:9093",
        "alerts": alerts
    }


def create_test_datetime(
        year: int = 2023,
        month: int = 10,
        day: int = 1,
        hour: int = 12,
        minute: int = 0,
        second: int = 0,
        tz: Optional[timezone] = timezone.utc
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
