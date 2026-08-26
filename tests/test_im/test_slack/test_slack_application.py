"""
Unit tests for SlackApplication class.

This module tests the SlackApplication class which extends the Application ABC
and provides Slack-specific functionality for incident management.
"""
from unittest.mock import Mock, AsyncMock, patch

import pytest
from app.config.validation import MessengerType
from app.im.slack.slack_application import SlackApplication
from app.im.slack.threads import slack_get_update_payload
from tests.utils import create_mock_incident_for_handlers, create_mock_http_response


class TestSlackApplication:
    """Test cases for SlackApplication class."""

    def test_closed_incident_update_payload_has_no_actions(self):
        """Closed incidents should not render action buttons."""
        incident = create_mock_incident_for_handlers(status="closed")
        incident.is_frozen = False

        with patch('app.im.slack.threads.get_config') as mock_get_config, \
                patch('app.im.slack.threads.get_environment_config') as mock_get_env_config:
            mock_get_config.return_value = Mock(app=Mock(task_management=False))
            mock_get_env_config.return_value = Mock(task_management_enabled=False)

            payload = slack_get_update_payload(incident, "body", "header", ":closed:", "UTC")

        assert len(payload['attachments']) == 1
        assert payload['attachments'][0]['text'] == "body"

    @pytest.mark.asyncio
    async def test_buttons_handler_take_it_posts_assignment_notification(self):
        """Take It should notify on new assignment instead of treating it as already assigned."""
        app = SlackApplication.__new__(SlackApplication)
        app.fetch_and_assign_user_name = Mock(side_effect=lambda incident, user_id, dump=True: setattr(incident, 'assigned_user_id', user_id))
        app.track_async_task = Mock()
        app.post_assignment_notification = AsyncMock()
        app._handle_freeze_button = AsyncMock()
        app._handle_task_action = Mock()
        app.form_body_header_status_icons = Mock(return_value=("body", "header", ":firing:"))
        app._get_user_timezone_str = Mock(return_value="UTC")

        incident = create_mock_incident_for_handlers()
        incidents = Mock()
        incidents.get_by_ts = Mock(return_value=incident)

        queue = Mock()
        queue.delete_by_id = AsyncMock()

        payload = {
            "token": "valid_token",
            "message_ts": incident.ts,
            "user": {"id": "U123"},
            "actions": [{"name": "chain"}],
            "original_message": {"text": "original"},
        }

        with patch('app.im.slack.slack_application.get_environment_config') as mock_get_env_config, \
                patch('app.im.slack.slack_application.slack_get_update_payload', return_value={"text": "updated"}), \
                patch('app.im.slack.slack_application.asyncio.create_task', return_value="assignment-task") as mock_create_task:
            mock_get_env_config.return_value = Mock(slack_verification_token="valid_token")
            result = await app.buttons_handler(payload, incidents, queue, Mock())

        assert result.status_code == 200
        app.fetch_and_assign_user_name.assert_called_once_with(incident, "U123", dump=False)
        app.post_assignment_notification.assert_called_once_with(incident)
        mock_create_task.assert_called_once()
        app.track_async_task.assert_called_once_with("assignment-task")
        assert incident.chain_enabled is False
        incident.dump.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_send_create_incident_message_success(self):
        """_send_create_incident_message returns ts on success."""
        app = SlackApplication.__new__(SlackApplication)
        app.type = MessengerType.SLACK
        app.post_message_url = 'https://slack.com/api/chat.postMessage'
        app.headers = {}
        app.thread_id_key = 'ts'
        mock_response = create_mock_http_response(status_code=200)
        mock_response.json = AsyncMock(return_value={'ok': True, 'ts': '1700000000.000100'})
        app.http = Mock()
        app.http.post = AsyncMock(return_value=mock_response)

        result = await app._send_create_incident_message({'channel': 'C1'})

        assert result == '1700000000.000100'

    @pytest.mark.asyncio
    async def test_send_create_incident_message_not_ok_returns_none(self):
        """Slack ok=False response must return None instead of the ts field."""
        app = SlackApplication.__new__(SlackApplication)
        app.type = MessengerType.SLACK
        app.post_message_url = 'https://slack.com/api/chat.postMessage'
        app.headers = {}
        app.thread_id_key = 'ts'
        mock_response = create_mock_http_response(status_code=200)
        mock_response.json = AsyncMock(return_value={'ok': False, 'error': 'channel_not_found'})
        app.http = Mock()
        app.http.post = AsyncMock(return_value=mock_response)

        result = await app._send_create_incident_message({'channel': 'C1'})

        assert result is None

    @pytest.mark.asyncio
    async def test_send_create_incident_message_http_error_returns_none(self):
        """Non-2xx HTTP response returns None."""
        app = SlackApplication.__new__(SlackApplication)
        app.type = MessengerType.SLACK
        app.post_message_url = 'https://slack.com/api/chat.postMessage'
        app.headers = {}
        app.thread_id_key = 'ts'
        mock_response = create_mock_http_response(status_code=500)
        mock_response.json = AsyncMock(return_value={'error': 'server_error'})
        app.http = Mock()
        app.http.post = AsyncMock(return_value=mock_response)

        result = await app._send_create_incident_message({'channel': 'C1'})

        assert result is None
