"""
Unit tests for app.im.mattermost.mattermost_application module.
"""
from unittest.mock import Mock, AsyncMock, patch

import pytest
from app.im.mattermost.mattermost_application import MattermostApplication
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

    @pytest.mark.asyncio
    async def test_buttons_handler_take_it_posts_assignment_notification(self):
        """Take It should post assignment notification for a new assignee."""
        app = MattermostApplication.__new__(MattermostApplication)
        app.fetch_and_assign_user_name = Mock(side_effect=lambda incident, user_id, dump=True: setattr(incident, 'assigned_user_id', user_id))
        app.track_async_task = Mock()
        app.post_assignment_notification = AsyncMock()
        app._handle_task_action = Mock()
        app._handle_unfreeze_action = AsyncMock()
        app._handle_freeze_action = AsyncMock()
        app._get_user_timezone_str = Mock(return_value="UTC")
        app.form_body_header_status_icons = Mock(return_value=("body", "header", ":firing:"))

        incident = create_mock_incident_for_handlers()
        incidents = Mock()
        incidents.get_by_ts = Mock(return_value=incident)

        queue = Mock()
        queue.delete_by_id = AsyncMock()

        payload = {
            "post_id": incident.ts,
            "user_id": "U123",
            "context": {"action": "chain"},
        }

        with patch('app.im.mattermost.mattermost_application.mattermost_get_button_update_payload', return_value={"update": "ok"}), \
                patch('app.im.mattermost.mattermost_application.asyncio.create_task', return_value="assignment-task") as mock_create_task:
            result = await app.buttons_handler(payload, incidents, queue, Mock())

        assert result.status_code == 200
        app.fetch_and_assign_user_name.assert_called_once_with(incident, "U123")
        app.post_assignment_notification.assert_called_once_with(incident)
        mock_create_task.assert_called_once()
        app.track_async_task.assert_called_once_with("assignment-task")
