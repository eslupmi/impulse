"""
Unit tests for app.im.mattermost.mattermost_application module.
"""
from unittest.mock import Mock, patch

from app.im.mattermost.threads import mattermost_get_update_payload
from tests.utils import create_mock_incident_for_handlers


class TestMattermostApplication:
    """Test cases for MattermostApplication class."""

    def test_closed_incident_update_payload_has_no_actions(self):
        """Closed incidents should not render action buttons."""
        incident = create_mock_incident_for_handlers(status="closed")
        incident.is_frozen = Mock(return_value=False)

        with patch('app.im.mattermost.threads.get_config') as mock_get_config, \
                patch('app.im.mattermost.threads.get_environment_config') as mock_get_env_config:
            mock_get_config.return_value = Mock(
                app=Mock(task_management=False),
                messenger=Mock(impulse_address="https://impulse.example.com")
            )
            mock_get_env_config.return_value = Mock(task_management_enabled=False)

            payload = mattermost_get_update_payload(incident, "body", "header", ":closed:", "UTC")

        attachment = payload['props']['attachments'][0]
        assert attachment['text'] == "body"
        assert 'actions' not in attachment
