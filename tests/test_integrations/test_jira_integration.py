"""Unit tests for JiraIntegration"""
from unittest.mock import AsyncMock, Mock

import pytest

from app.integrations.jira_client import JiraClient
from app.integrations.jira_integration import JiraIntegration
from tests.utils import create_mock_incident_for_handlers, create_alert_payload, create_mock_queue


class TestJiraIntegration:
    """Test suite for JiraIntegration class"""
    
    @pytest.fixture
    def mock_jira_client(self):
        """Fixture for mock JiraClient"""
        client = Mock(spec=JiraClient)
        client.create_issue = AsyncMock()
        return client
    
    @pytest.fixture
    def jira_integration(self, mock_jira_client):
        """Fixture for JiraIntegration instance"""
        return JiraIntegration(mock_jira_client, "DTS")
    
    @pytest.fixture
    def mock_incident(self):
        """Fixture for mock incident"""
        payload = create_alert_payload(
            status="firing",
            alertname="TestAlert",
            service="test-service"
        )
        incident = create_mock_incident_for_handlers(
            uuid="test-uuid-123",
            status="firing",
            payload=payload
        )
        incident.task_link = ""
        incident.assigned_fullname = "Test User"
        return incident
    
    @pytest.fixture
    def mock_queue(self):
        """Fixture for mock queue"""
        return create_mock_queue()
    
    def test_initialization(self, mock_jira_client):
        """Test JiraIntegration initialization"""
        integration = JiraIntegration(mock_jira_client, "TEST")
        assert integration.jira_client == mock_jira_client
        assert integration.project_key == "TEST"
    
    def test_format_incident_with_group_labels(self, jira_integration, mock_incident):
        """Test formatting incident with group labels"""
        summary, description = jira_integration.format_incident_for_jira(mock_incident)
        
        assert "Alert:" in summary
        assert "alertname=TestAlert" in summary or "service=test-service" in summary
        assert "Incident Status:" in description
        assert "Assigned to: Test User" in description
        assert "Alerts Count:" in description
    
    def test_format_incident_without_group_labels(self, jira_integration):
        """Test formatting incident without group labels"""
        payload = {
            'groupLabels': {},
            'alerts': [
                {
                    'labels': {'alertname': 'FallbackAlert'},
                    'annotations': {}
                }
            ]
        }
        incident = create_mock_incident_for_handlers(payload=payload)
        incident.assigned_fullname = ""
        incident.link = ""
        
        summary, description = jira_integration.format_incident_for_jira(incident)
        
        assert "Alert: FallbackAlert" in summary
        assert "Incident Status:" in description
    
    def test_format_incident_no_alerts(self, jira_integration):
        """Test formatting incident with no alerts"""
        payload = {'groupLabels': {}, 'alerts': []}
        incident = create_mock_incident_for_handlers(payload=payload)
        incident.assigned_fullname = ""
        incident.link = ""
        
        summary, _ = jira_integration.format_incident_for_jira(incident)
        
        assert "Incident Alert" in summary
    
    def test_format_incident_truncates_long_summary(self, jira_integration):
        """Test that long summary is truncated to 255 chars"""
        long_label_value = "a" * 300
        payload = {
            'groupLabels': {'very_long_label': long_label_value},
            'alerts': []
        }
        incident = create_mock_incident_for_handlers(payload=payload)
        incident.assigned_fullname = ""
        incident.link = ""
        
        summary, _ = jira_integration.format_incident_for_jira(incident)
        
        assert len(summary) <= 255
        assert summary.endswith("...")
    
    def test_format_incident_includes_im_thread_link(self, jira_integration, mock_incident):
        """Test that IM thread link is included in description"""
        mock_incident.link = "https://slack.com/archives/C123/p456"
        
        _, description = jira_integration.format_incident_for_jira(mock_incident)
        
        assert "IM Thread: https://slack.com/archives/C123/p456" in description
    
    def test_format_incident_truncates_long_label_values(self, jira_integration):
        """Test that long label values are truncated"""
        long_value = "x" * 300
        payload = {
            'groupLabels': {'key': long_value},
            'alerts': []
        }
        incident = create_mock_incident_for_handlers(payload=payload)
        incident.assigned_fullname = ""
        incident.link = ""
        
        _, description = jira_integration.format_incident_for_jira(incident)
        
        # Check that the description contains truncated value
        assert "..." in description
    
    @pytest.mark.asyncio
    async def test_handle_button_press_task_already_exists(self, jira_integration, mock_incident, mock_queue):
        """Test button press when task already exists"""
        mock_incident.task_link = "https://jira.com/browse/DTS-123"
        
        result = await jira_integration.handle_button_press(mock_incident, mock_queue)
        
        assert result["success"] is True
        assert result["message"] == "Task already exists"
        # Verify create_issue was not called
        jira_integration.jira_client.create_issue.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_button_press_success(self, jira_integration, mock_incident, mock_queue):
        """Test successful button press and task creation"""
        jira_integration.jira_client.create_issue.return_value = {
            "key": "DTS-456",
            "url": "https://jira.com/browse/DTS-456"
        }
        
        result = await jira_integration.handle_button_press(mock_incident, mock_queue)
        
        assert result["success"] is True
        assert result["message"] == "Created Jira task: DTS-456"
        assert result["task_key"] == "DTS-456"
        assert result["task_url"] == "https://jira.com/browse/DTS-456"
        
        # Verify incident was updated
        assert mock_incident.task_link == "https://jira.com/browse/DTS-456"
        mock_incident.dump.assert_called_once()
        
        # Verify queue.put was called with update_message type
        mock_queue.put.assert_called_once()
        call_args = mock_queue.put.call_args[1]
        assert call_args['type_'] == 'update_message'
        assert call_args['incident_uuid'] == mock_incident.uuid
    
    @pytest.mark.asyncio
    async def test_handle_button_press_failure(self, jira_integration, mock_incident, mock_queue):
        """Test button press when task creation fails"""
        jira_integration.jira_client.create_issue.return_value = None
        
        result = await jira_integration.handle_button_press(mock_incident, mock_queue)
        
        assert result["success"] is False
        assert result["message"] == "Failed to create Jira task"
        
        # Verify incident was not updated
        assert mock_incident.task_link == ""
        mock_incident.dump.assert_not_called()
        
        # Verify queue.put was not called
        mock_queue.put.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_button_press_uses_correct_project_key(self, jira_integration, mock_incident, mock_queue):
        """Test that button press uses configured project key"""
        jira_integration.jira_client.create_issue.return_value = {
            "key": "DTS-789",
            "url": "https://jira.com/browse/DTS-789"
        }
        
        await jira_integration.handle_button_press(mock_incident, mock_queue)
        
        # Verify create_issue was called with correct project key
        call_args = jira_integration.jira_client.create_issue.call_args[1]
        assert call_args['project_key'] == "DTS"
    
    def test_format_incident_alerts_count(self, jira_integration):
        """Test that alerts count is correctly included"""
        payload = create_alert_payload(multiple_alerts=True)
        payload['alerts'].append({
            'status': 'firing',
            'labels': {'alertname': 'Alert3'},
            'annotations': {}
        })
        incident = create_mock_incident_for_handlers(payload=payload)
        incident.assigned_fullname = ""
        incident.link = ""
        
        _, description = jira_integration.format_incident_for_jira(incident)
        
        # Should have 3 alerts (base + multiple_alerts + one we added)
        assert "Alerts Count: 3" in description

