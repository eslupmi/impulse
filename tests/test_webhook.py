"""
Unit tests for the Webhook class and related functionality.
"""
import asyncio
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from aiohttp import ClientSession, BasicAuth

from app.config.validation import WebhookConfig
from app.incident.incident import Incident, IncidentConfig
from app.webhook import Webhook, generate_webhooks
from tests.utils import setup_mock_session_class_patch


class TestWebhook:
    """Test cases for the Webhook class."""

    @pytest.fixture
    def sample_incident(self):
        """Create a sample incident for testing."""
        config = IncidentConfig(
            application_type="slack",
            application_url="https://test.slack.com",
            application_team="test-team"
        )
        return Incident(
            payload={"alertname": "TestAlert", "severity": "critical"},
            status="firing",
            channel_id="C123456789",
            config=config,
            status_update_datetime="2023-10-01T10:00:00Z",
            assigned_user_id="U123456789",
            assigned_user="testuser",
            assigned_fullname="Test User",
            messenger_type="slack"
        )

    @pytest.fixture
    def mock_session(self):
        """Create a mock aiohttp session."""
        session = AsyncMock(spec=ClientSession)
        mock_response = AsyncMock()
        mock_response.status = 200
        session.post.return_value.__aenter__.return_value = mock_response
        return session

    def test_webhook_initialization_basic(self):
        """Test basic webhook initialization."""
        webhook = Webhook("https://example.com/webhook")

        assert webhook._url == "https://example.com/webhook"
        assert webhook._data is None
        assert webhook._json_payload is None
        assert webhook._auth is None

    def test_webhook_initialization_with_data(self):
        """Test webhook initialization with form data."""
        data = {"message": "test", "severity": "high"}
        webhook = Webhook("https://example.com/webhook", data=data)

        assert webhook._url == "https://example.com/webhook"
        assert webhook._data == data
        assert webhook._json_payload is None

    def test_webhook_initialization_with_json_dict(self):
        """Test webhook initialization with JSON dict payload."""
        json_payload = {"message": "test", "severity": "high"}
        webhook = Webhook("https://example.com/webhook", json_payload=json_payload)

        assert webhook._url == "https://example.com/webhook"
        assert webhook._json_payload == json_payload
        assert webhook._data is None

    def test_webhook_initialization_with_json_string(self):
        """Test webhook initialization with JSON string payload."""
        json_payload = '{"message": "test", "severity": "high"}'
        webhook = Webhook("https://example.com/webhook", json_payload=json_payload)

        assert webhook._url == "https://example.com/webhook"
        assert webhook._json_payload == json_payload

    def test_webhook_initialization_with_auth(self):
        """Test webhook initialization with authentication."""
        webhook = Webhook("https://example.com/webhook", auth="user:pass")

        assert webhook._auth == "user:pass"

    @pytest.mark.asyncio
    async def test_push_with_session_form_data(self, mock_session, sample_incident):
        """Test push method with form data using provided session."""
        data = {"message": "Alert: {{ incident.payload.alertname }}"}
        webhook = Webhook("https://example.com/webhook", data=data)

        result = await webhook.push(incident=sample_incident, session=mock_session)

        assert result == ('ok', 200)
        mock_session.post.assert_called_once()

        # Verify the call was made with form data
        call_args = mock_session.post.call_args
        assert call_args[1]['data'] == {"message": "Alert: TestAlert"}

    @pytest.mark.asyncio
    async def test_push_with_session_json_dict(self, mock_session, sample_incident):
        """Test push method with JSON dict using provided session."""
        json_payload = {"message": "Alert: {{ incident.payload.alertname }}",
                        "severity": "{{ incident.payload.severity }}"}
        webhook = Webhook("https://example.com/webhook", json_payload=json_payload)

        result = await webhook.push(incident=sample_incident, session=mock_session)

        assert result == ('ok', 200)
        mock_session.post.assert_called_once()

        # Verify the call was made with JSON data
        call_args = mock_session.post.call_args
        assert call_args[1]['json'] == {"message": "Alert: TestAlert", "severity": "critical"}

    @pytest.mark.asyncio
    async def test_push_with_session_json_string(self, mock_session, sample_incident):
        """Test push method with JSON string using provided session."""
        json_payload = '{"message": "Alert: {{ incident.payload.alertname }}"}'
        webhook = Webhook("https://example.com/webhook", json_payload=json_payload)

        result = await webhook.push(incident=sample_incident, session=mock_session)

        assert result == ('ok', 200)
        mock_session.post.assert_called_once()

        # Verify the call was made with JSON string
        call_args = mock_session.post.call_args
        assert call_args[1]['data'] == '{"message": "Alert: TestAlert"}'
        assert call_args[1]['headers']['Content-Type'] == 'application/json'

    @pytest.mark.asyncio
    async def test_push_without_session(self, sample_incident):
        """Test push method without provided session (creates temporary session)."""
        with patch('aiohttp.ClientSession') as mock_session_class:
            setup_mock_session_class_patch(mock_session_class, 200)

            webhook = Webhook("https://example.com/webhook", data={"message": "test"})
            result = await webhook.push(incident=sample_incident)

            assert result == ('ok', 200)
            mock_session_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_push_with_auth(self, mock_session, sample_incident):
        """Test push method with authentication."""
        webhook = Webhook("https://example.com/webhook", data={"message": "test"}, auth="user:pass")

        result = await webhook.push(incident=sample_incident, session=mock_session)

        assert result == ('ok', 200)
        call_args = mock_session.post.call_args
        assert isinstance(call_args[1]['auth'], BasicAuth)

    @pytest.mark.asyncio
    async def test_make_request_timeout_error(self, mock_session, sample_incident):
        """Test _make_request method with timeout error."""
        mock_session.post.side_effect = asyncio.TimeoutError()

        webhook = Webhook("https://example.com/webhook", data={"message": "test"})
        result = await webhook.push(incident=sample_incident, session=mock_session)

        assert result == ('Timeout', None)

    @pytest.mark.asyncio
    async def test_make_request_connection_error(self, mock_session, sample_incident):
        """Test _make_request method with connection error."""
        mock_session.post.side_effect = aiohttp.ClientConnectionError()

        webhook = Webhook("https://example.com/webhook", data={"message": "test"})
        result = await webhook.push(incident=sample_incident, session=mock_session)

        assert result == ('ConnectionError', None)

    @pytest.mark.asyncio
    async def test_make_request_client_error(self, mock_session, sample_incident):
        """Test _make_request method with client error."""
        mock_session.post.side_effect = aiohttp.ClientError("Test error")

        webhook = Webhook("https://example.com/webhook", data={"message": "test"})
        result = await webhook.push(incident=sample_incident, session=mock_session)

        assert result == ('ClientError', None)

    def test_render_data_with_incident(self, sample_incident):
        """Test _render_data method with incident."""
        data = {
            "message": "Alert: {{ incident.payload.alertname }}",
            "severity": "{{ incident.payload.severity }}"
        }
        webhook = Webhook("https://example.com/webhook", data=data)

        rendered_data = webhook._render_data(sample_incident)

        assert rendered_data == {
            "message": "Alert: TestAlert",
            "severity": "critical"
        }

    def test_render_data_without_incident(self):
        """Test _render_data method without incident."""
        data = {"message": "Static message"}
        webhook = Webhook("https://example.com/webhook", data=data)

        rendered_data = webhook._render_data()

        assert rendered_data == {"message": "Static message"}

    def test_render_data_without_pre_render_data(self, sample_incident):
        """Test _render_data method without pre_render_data."""
        webhook = Webhook("https://example.com/webhook")

        rendered_data = webhook._render_data(sample_incident)

        assert rendered_data == {}

    def test_render_json_string_with_incident(self, sample_incident):
        """Test _render_json method with JSON string and incident."""
        json_payload = '{"message": "Alert: {{ incident.payload.alertname }}"}'
        webhook = Webhook("https://example.com/webhook", json_payload=json_payload)

        rendered_json = webhook._render_json(sample_incident)

        assert rendered_json == '{"message": "Alert: TestAlert"}'

    def test_render_json_dict_with_incident(self, sample_incident):
        """Test _render_json method with JSON dict and incident."""
        json_payload = {
            "message": "Alert: {{ incident.payload.alertname }}",
            "severity": "{{ incident.payload.severity }}"
        }
        webhook = Webhook("https://example.com/webhook", json_payload=json_payload)

        rendered_json = webhook._render_json(sample_incident)

        assert rendered_json == {
            "message": "Alert: TestAlert",
            "severity": "critical"
        }

    def test_render_json_without_incident(self):
        """Test _render_json method without incident."""
        json_payload = {"message": "Static message"}
        webhook = Webhook("https://example.com/webhook", json_payload=json_payload)

        rendered_json = webhook._render_json()

        assert rendered_json == {"message": "Static message"}

    def test_render_json_none(self, sample_incident):
        """Test _render_json method when json_payload is None."""
        webhook = Webhook("https://example.com/webhook")

        rendered_json = webhook._render_json(sample_incident)

        assert rendered_json is None

    def test_render_nested_dict(self, sample_incident):
        """Test _render_nested_dict method with nested data."""
        webhook = Webhook("https://example.com/webhook")

        data = {
            "message": "Alert: {{ incident.payload.alertname }}",
            "details": {
                "severity": "{{ incident.payload.severity }}",
                "nested": {
                    "value": "{{ incident.payload.alertname }}"
                }
            },
            "list": [
                "{{ incident.payload.alertname }}",
                {"key": "{{ incident.payload.severity }}"}
            ]
        }

        rendered = webhook._render_nested_dict(data, sample_incident.serialize())

        expected = {
            "message": "Alert: TestAlert",
            "details": {
                "severity": "critical",
                "nested": {
                    "value": "TestAlert"
                }
            },
            "list": [
                "TestAlert",
                {"key": "critical"}
            ]
        }

        assert rendered == expected

    def test_render_nested_dict_non_string_values(self):
        """Test _render_nested_dict method with non-string values."""
        webhook = Webhook("https://example.com/webhook")

        data = {
            "string": "test",
            "number": 123,
            "boolean": True,
            "none": None
        }

        rendered = webhook._render_nested_dict(data, {})

        assert rendered == data

    def test_get_auth(self):
        """Test _get_auth method."""
        webhook = Webhook("https://example.com/webhook", auth="user:pass")

        auth = webhook._get_auth()

        assert isinstance(auth, BasicAuth)
        assert auth.login == "user"
        assert auth.password == "pass"

    def test_render_static_method(self):
        """Test render static method."""
        result = Webhook.render("Hello {{ name }}", name="World")
        assert result == "Hello World"

    def test_render_static_method_with_env(self):
        """Test render static method with environment variables."""
        with patch.dict('os.environ', {'TEST_VAR': 'test_value'}):
            result = Webhook.render("Hello {{ env.TEST_VAR }}")
            assert result == "Hello test_value"


class TestGenerateWebhooks:
    """Test cases for the generate_webhooks function."""

    def test_generate_webhooks_empty(self):
        """Test generate_webhooks with empty config."""
        webhooks = generate_webhooks()
        assert webhooks == {}

    def test_generate_webhooks_with_config(self):
        """Test generate_webhooks with webhook configuration."""
        webhook_config = {
            "test_webhook": WebhookConfig(
                url="https://example.com/webhook",
                data={"message": "test"},
                auth="user:pass"
            ),
            "json_webhook": WebhookConfig(
                url="https://example.com/json",
                json={"message": "test"}  # Use the alias 'json' instead of 'json_payload'
            )
        }

        webhooks = generate_webhooks(webhook_config)

        assert len(webhooks) == 2
        assert "test_webhook" in webhooks
        assert "json_webhook" in webhooks

        # Test first webhook
        test_webhook = webhooks["test_webhook"]
        assert test_webhook._url == "https://example.com/webhook"
        assert test_webhook._data == {"message": "test"}
        assert test_webhook._auth == "user:pass"

        # Test second webhook
        json_webhook = webhooks["json_webhook"]
        assert json_webhook._url == "https://example.com/json"
        assert json_webhook._json_payload == {"message": "test"}

    def test_generate_webhooks_none_config(self):
        """Test generate_webhooks with None config."""
        webhooks = generate_webhooks(None)
        assert webhooks == {}


class TestWebhookIntegration:
    """Integration tests for webhook functionality."""

    @pytest.mark.asyncio
    async def test_complete_webhook_flow_form_data(self, sample_incident):
        """Test complete webhook flow with form data."""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session, _ = setup_mock_session_class_patch(mock_session_class, 201)

            webhook = Webhook(
                url="https://example.com/webhook",
                data={
                    "alert": "{{ incident.payload.commonLabels.alertname }}",
                    "severity": "{{ incident.payload.commonLabels.severity }}"
                },
                auth="user:pass"
            )

            result = await webhook.push(incident=sample_incident)

            assert result == ('ok', 201)
            mock_session.post.assert_called_once()

            # Verify the call parameters
            call_args = mock_session.post.call_args
            assert call_args[1]['url'] == "https://example.com/webhook"
            assert call_args[1]['data'] == {
                "alert": "TestAlert",
                "severity": "critical"
            }
            assert isinstance(call_args[1]['auth'], BasicAuth)

    @pytest.mark.asyncio
    async def test_complete_webhook_flow_json_dict(self, sample_incident):
        """Test complete webhook flow with JSON dict."""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session, _ = setup_mock_session_class_patch(mock_session_class, 200)

            webhook = Webhook(
                url="https://example.com/webhook",
                json_payload={
                    "alert": "{{ incident.payload.commonLabels.alertname }}",
                    "severity": "{{ incident.payload.commonLabels.severity }}"
                }
            )

            result = await webhook.push(incident=sample_incident)

            assert result == ('ok', 200)
            mock_session.post.assert_called_once()

            # Verify the call parameters
            call_args = mock_session.post.call_args
            assert call_args[1]['url'] == "https://example.com/webhook"
            assert call_args[1]['json'] == {
                "alert": "TestAlert",
                "severity": "critical"
            }

    @pytest.mark.asyncio
    async def test_complete_webhook_flow_json_string(self, sample_incident):
        """Test complete webhook flow with JSON string."""
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session, _ = setup_mock_session_class_patch(mock_session_class, 200)

            webhook = Webhook(
                url="https://example.com/webhook",
                json_payload='{"alert": "{{ incident.payload.commonLabels.alertname }}"}'
            )

            result = await webhook.push(incident=sample_incident)

            assert result == ('ok', 200)
            mock_session.post.assert_called_once()

            # Verify the call parameters
            call_args = mock_session.post.call_args
            assert call_args[1]['url'] == "https://example.com/webhook"
            assert call_args[1]['data'] == '{"alert": "TestAlert"}'
            assert call_args[1]['headers']['Content-Type'] == 'application/json'
