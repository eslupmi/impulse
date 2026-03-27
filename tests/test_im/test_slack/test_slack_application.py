"""
Unit tests for SlackApplication class.

This module tests the SlackApplication class which extends the Application ABC
and provides Slack-specific functionality for incident management.
"""
from unittest.mock import Mock, patch

from app.im.slack.threads import slack_get_update_payload
from tests.utils import create_mock_incident_for_handlers


class TestSlackApplication:
    """Test cases for SlackApplication class."""

    def test_closed_incident_update_payload_has_no_actions(self):
        """Closed incidents should not render action buttons."""
        incident = create_mock_incident_for_handlers(status="closed")
        incident.is_frozen = Mock(return_value=False)

        with patch('app.im.slack.threads.get_config') as mock_get_config, \
                patch('app.im.slack.threads.get_environment_config') as mock_get_env_config:
            mock_get_config.return_value = Mock(app=Mock(task_management=False))
            mock_get_env_config.return_value = Mock(task_management_enabled=False)

            payload = slack_get_update_payload(incident, "body", "header", ":closed:", "UTC")

        assert len(payload['attachments']) == 1
        assert payload['attachments'][0]['text'] == "body"
