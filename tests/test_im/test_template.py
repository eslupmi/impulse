"""
Unit tests for app.im.template module.
"""
from unittest.mock import Mock

import pytest

from app.jinja_template import JinjaTemplate


class TestJinjaTemplate:
    """Test cases for JinjaTemplate class."""

    def test_jinja_template_creation(self):
        """Test creating a JinjaTemplate instance."""
        template_str = "Hello {{ name }}!"
        template = JinjaTemplate(template_str)

        assert template.template == template_str

    def test_form_message_with_alert_state(self):
        """Test form_message with alert state only."""
        template_str = "Alert: {{ payload.status }}"
        template = JinjaTemplate(template_str)

        alert_state = {"status": "firing"}
        result = template.form_message(alert_state)

        assert "Alert: firing" in result

    def test_form_message_with_incident(self):
        """Test form_message with incident data."""
        template_str = "Incident: {{ incident.status }}"
        template = JinjaTemplate(template_str)

        # Mock incident
        mock_incident = Mock()
        mock_incident.serialize.return_value = {"status": "firing"}

        alert_state = {"status": "firing"}
        result = template.form_message(alert_state, mock_incident)

        assert "Incident: firing" in result
        mock_incident.serialize.assert_called_once()

    def test_form_message_without_incident(self):
        """Test form_message without incident (None)."""
        template_str = "Alert: {{ payload.status }}"
        template = JinjaTemplate(template_str)

        alert_state = {"status": "resolved"}
        result = template.form_message(alert_state)

        assert "Alert: resolved" in result

    def test_form_notification(self):
        """Test form_notification method."""
        template_str = "Notification: {{ fields.message }}"
        template = JinjaTemplate(template_str)

        fields = {"message": "Test notification"}
        result = template.form_notification(fields)

        assert "Notification: Test notification" in result

    def test_form_notification_with_multiple_fields(self):
        """Test form_notification with multiple fields."""
        template_str = "User: {{ fields.user }}, Status: {{ fields.status }}"
        template = JinjaTemplate(template_str)

        fields = {"user": "testuser", "status": "active"}
        result = template.form_notification(fields)

        assert "User: testuser" in result
        assert "Status: active" in result

    def test_template_with_conditionals(self):
        """Test template with conditional logic."""
        template_str = "{% if payload.status == 'firing' %}ALERT{% else %}OK{% endif %}"
        template = JinjaTemplate(template_str)

        # Test firing condition
        alert_state = {"status": "firing"}
        result = template.form_message(alert_state)
        assert "ALERT" in result

        # Test non-firing condition
        alert_state = {"status": "resolved"}
        result = template.form_message(alert_state)
        assert "OK" in result

    def test_template_with_loops(self):
        """Test template with loop logic."""
        template_str = "Users: {% for user in fields.users %}{{ user }}{% if not loop.last %}, {% endif %}{% endfor %}"
        template = JinjaTemplate(template_str)

        fields = {"users": ["user1", "user2", "user3"]}
        result = template.form_notification(fields)

        assert "Users: user1, user2, user3" in result

    def test_empty_template(self):
        """Test template with empty string."""
        template = JinjaTemplate("")

        alert_state = {"status": "firing"}
        result = template.form_message(alert_state)

        assert result == ""

    def test_template_with_special_characters(self):
        """Test template with special characters."""
        template_str = "Special: {{ payload.message }}"
        template = JinjaTemplate(template_str)

        alert_state = {"message": "Test & <special> characters"}
        result = template.form_message(alert_state)

        assert "Special: Test & <special> characters" in result
