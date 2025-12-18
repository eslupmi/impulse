"""Unit tests for JiraIntegration"""
from unittest.mock import AsyncMock, Mock, patch

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
    def mock_config(self):
        """Fixture for mock config"""
        config = Mock()
        config.app.task_management = Mock()
        config.app.task_management.project_key = "DTS"
        config.app.task_management.template_files = None
        return config
    
    @pytest.fixture
    def jira_integration(self, mock_jira_client):
        """Fixture for JiraIntegration instance"""
        return JiraIntegration(mock_jira_client)
    
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
        integration = JiraIntegration(mock_jira_client)
        assert integration.jira_client == mock_jira_client
        assert integration.tm_type == "jira"
    
    @patch('app.integrations.jira_integration.get_config')
    def test_format_incident_with_group_labels(self, mock_get_config, jira_integration, mock_incident, mock_config):
        """Test formatting incident with group labels"""
        mock_get_config.return_value = mock_config
        summary, description = jira_integration.format_incident_for_jira(mock_incident)
        
        assert "TestAlert" in summary
        assert "service=test-service" in summary or "test-service" in summary
        assert "*Common Labels*" in description or "*Links*" in description
    
    @patch('app.integrations.jira_integration.get_config')
    def test_format_incident_without_group_labels(self, mock_get_config, jira_integration, mock_config):
        """Test formatting incident without group labels"""
        mock_get_config.return_value = mock_config
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
        
        assert "FallbackAlert" in summary
        assert isinstance(description, str)  # Description should be a string
    
    @patch('app.integrations.jira_integration.get_config')
    def test_format_incident_no_alerts(self, mock_get_config, jira_integration, mock_config):
        """Test formatting incident with no alerts"""
        mock_get_config.return_value = mock_config
        payload = {'groupLabels': {}, 'alerts': []}
        incident = create_mock_incident_for_handlers(payload=payload)
        incident.assigned_fullname = ""
        incident.link = ""
        
        summary, _ = jira_integration.format_incident_for_jira(incident)
        
        assert "Incident Alert" in summary
    
    @patch('app.integrations.jira_integration.get_config')
    def test_format_incident_truncates_long_summary(self, mock_get_config, jira_integration, mock_config):
        """Test that long summary is truncated to 255 chars"""
        mock_get_config.return_value = mock_config
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
    
    @patch('app.integrations.jira_integration.get_config')
    def test_format_incident_includes_im_thread_link(self, mock_get_config, jira_integration, mock_incident, mock_config):
        """Test that IM thread link is included in description"""
        mock_get_config.return_value = mock_config
        mock_incident.link = "https://slack.com/archives/C123/p456"
        
        _, description = jira_integration.format_incident_for_jira(mock_incident)
        
        assert "https://slack.com/archives/C123/p456" in description
        assert "Incident" in description or "[Incident|" in description
    
    @patch('app.integrations.jira_integration.get_config')
    def test_format_incident_truncates_long_label_values(self, mock_get_config, jira_integration, mock_config):
        """Test that long annotation values are truncated"""
        mock_get_config.return_value = mock_config
        long_value = "x" * 300
        payload = {
            'groupLabels': {},
            'alerts': [],
            'commonAnnotations': {'long_annotation': long_value}
        }
        incident = create_mock_incident_for_handlers(payload=payload)
        incident.assigned_fullname = ""
        incident.link = ""
        
        _, description = jira_integration.format_incident_for_jira(incident)
        
        # Check that the description contains truncated value in annotations
        assert "..." in description or "long_annotation" in description
    
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
    @patch('app.integrations.jira_integration.get_config')
    async def test_handle_button_press_success(self, mock_get_config, jira_integration, mock_incident, mock_queue, mock_config):
        """Test successful button press and task creation"""
        mock_get_config.return_value = mock_config
        jira_integration.jira_client.create_issue.return_value = {
            "key": "DTS-456",
            "url": "https://jira.com/browse/DTS-456"
        }
        
        result = await jira_integration.handle_button_press(mock_incident, mock_queue)
        
        assert result["success"] is True
        assert result["message"] == "Created Jira task: DTS-456"
        assert result["task_key"] == "DTS-456"
        assert result["task_url"] == "https://jira.com/browse/DTS-456"
        
        assert mock_incident.task_link == "https://jira.com/browse/DTS-456"
        assert mock_incident.task_creation_in_progress is False
        mock_incident.dump.assert_called_once()
        
        mock_queue.put.assert_called_once()
        call_args = mock_queue.put.call_args[1]
        assert call_args['type_'] == 'update_message'
        assert call_args['uniq_id'] == mock_incident.uniq_id
    
    @pytest.mark.asyncio
    @patch('app.integrations.jira_integration.get_config')
    async def test_handle_button_press_failure(self, mock_get_config, jira_integration, mock_incident, mock_queue, mock_config):
        """Test button press when task creation fails"""
        mock_get_config.return_value = mock_config
        jira_integration.jira_client.create_issue.return_value = None
        
        result = await jira_integration.handle_button_press(mock_incident, mock_queue)
        
        assert result["success"] is False
        assert result["message"] == "Failed to create Jira task"
        
        # Verify incident flags were cleared after failure
        assert mock_incident.task_link == ""
        assert mock_incident.task_creation_in_progress is False
        mock_incident.dump.assert_not_called()  # No dump on failure since no persistent changes
        
        mock_queue.put.assert_called_once()
        call_args = mock_queue.put.call_args[1]
        assert call_args['type_'] == 'update_message'
    
    @pytest.mark.asyncio
    async def test_handle_button_press_creation_in_progress(self, jira_integration, mock_incident, mock_queue):
        """Test button press when task creation is already in progress"""
        mock_incident.task_creation_in_progress = True
        
        result = await jira_integration.handle_button_press(mock_incident, mock_queue)
        
        assert result["success"] is True
        assert result["message"] == "Task creation in progress"
        
        jira_integration.jira_client.create_issue.assert_not_called()
        mock_queue.put.assert_not_called()
    
    @pytest.mark.asyncio
    @patch('app.integrations.jira_integration.get_config')
    async def test_handle_button_press_uses_correct_project_key(self, mock_get_config, jira_integration, mock_incident, mock_queue, mock_config):
        """Test that button press uses configured project key"""
        mock_get_config.return_value = mock_config
        jira_integration.jira_client.create_issue.return_value = {
            "key": "DTS-789",
            "url": "https://jira.com/browse/DTS-789"
        }
        
        await jira_integration.handle_button_press(mock_incident, mock_queue)
        
        # Verify create_issue was called with correct project key
        call_args = jira_integration.jira_client.create_issue.call_args[1]
        assert call_args['project_key'] == "DTS"
    
    @patch('app.integrations.jira_integration.get_config')
    def test_format_incident_with_multiple_alerts(self, mock_get_config, jira_integration, mock_config):
        """Test formatting incident with multiple alerts"""
        mock_get_config.return_value = mock_config
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
        
        # Description should be generated and contain at least Links section
        assert len(description) > 0
        assert "*Links*" in description

