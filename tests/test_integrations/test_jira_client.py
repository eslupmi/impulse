"""Unit tests for JiraClient"""
import base64
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.integrations.jira_client import JiraClient
from tests.utils import MockContextManager


class TestJiraClient:
    """Test suite for JiraClient class"""
    
    @pytest.fixture
    def jira_credentials(self):
        """Fixture for Jira credentials"""
        return {
            "base_url": "https://test.atlassian.net",
            "user_email": "test@example.com",
            "api_token": "test_token_123"
        }
    
    @pytest.fixture
    def jira_client(self, jira_credentials):
        """Fixture for JiraClient instance"""
        return JiraClient(**jira_credentials)
    
    def test_initialization(self, jira_client, jira_credentials):
        """Test JiraClient initialization"""
        assert jira_client.base_url == jira_credentials["base_url"]
        assert jira_client.user_email == jira_credentials["user_email"]
        assert jira_client.api_token == jira_credentials["api_token"]
        
        # Verify auth token is properly base64 encoded
        expected_credentials = f"{jira_credentials['user_email']}:{jira_credentials['api_token']}"
        expected_token = base64.b64encode(expected_credentials.encode()).decode('ascii')
        assert jira_client._auth_token == expected_token
    
    def test_initialization_strips_trailing_slash(self):
        """Test that base_url trailing slash is stripped"""
        client = JiraClient(
            base_url="https://test.atlassian.net/",
            user_email="test@example.com",
            api_token="token"
        )
        assert client.base_url == "https://test.atlassian.net"
    
    def test_get_auth_headers(self, jira_client):
        """Test _get_auth_headers returns correct format"""
        headers = jira_client._get_auth_headers()
        
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"
    
    @pytest.mark.asyncio
    async def test_create_issue_success(self, jira_client):
        """Test successful issue creation"""
        # Mock response
        mock_response = AsyncMock()
        mock_response.status = 201
        mock_response.json = AsyncMock(return_value={"key": "DTS-123"})
        
        # Mock the HTTP client completely
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)
        
        # Replace the HTTP client
        jira_client._http_client = mock_http_client
        
        result = await jira_client.create_issue(
            project_key="DTS",
            summary="Test Issue",
            description="Test Description"
        )
        
        assert result is not None
        assert result["key"] == "DTS-123"
        assert result["url"] == "https://test.atlassian.net/browse/DTS-123"
    
    @pytest.mark.asyncio
    async def test_create_issue_failure_non_201(self, jira_client):
        """Test issue creation failure with non-201 status"""
        # Mock response
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Bad Request")
        
        # Mock HTTP client
        with patch.object(jira_client._http_client, 'post') as mock_post:
            mock_post.return_value = MockContextManager(mock_response)
            
            with patch.object(jira_client._http_client, '__aenter__', return_value=jira_client._http_client):
                with patch.object(jira_client._http_client, '__aexit__', return_value=None):
                    result = await jira_client.create_issue(
                        project_key="DTS",
                        summary="Test Issue",
                        description="Test Description"
                    )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_create_issue_exception(self, jira_client):
        """Test issue creation with exception"""
        # Mock HTTP client to raise exception
        with patch.object(jira_client._http_client, 'post', side_effect=Exception("Network error")):
            with patch.object(jira_client._http_client, '__aenter__', return_value=jira_client._http_client):
                with patch.object(jira_client._http_client, '__aexit__', return_value=None):
                    result = await jira_client.create_issue(
                        project_key="DTS",
                        summary="Test Issue",
                        description="Test Description"
                    )
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_create_issue_failure_with_error_text(self, jira_client):
        """Test issue creation failure with detailed error text"""
        # Mock response with error details
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value='{"errorMessages":["Project does not exist"],"errors":{}}')
        
        # Mock the HTTP client completely
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=None)
        
        # Replace the HTTP client
        jira_client._http_client = mock_http_client
        
        result = await jira_client.create_issue(
            project_key="INVALID",
            summary="Test Issue",
            description="Test Description"
        )
        
        assert result is None
        # Verify text() was called to get error details
        mock_response.text.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_issue_payload_format(self, jira_client):
        """Test that create_issue sends correct payload format"""
        mock_response = AsyncMock()
        mock_response.status = 201
        mock_response.json = AsyncMock(return_value={"key": "DTS-123"})
        
        with patch.object(jira_client._http_client, 'post') as mock_post:
            mock_post.return_value = MockContextManager(mock_response)
            
            with patch.object(jira_client._http_client, '__aenter__', return_value=jira_client._http_client):
                with patch.object(jira_client._http_client, '__aexit__', return_value=None):
                    await jira_client.create_issue(
                        project_key="DTS",
                        summary="Test Summary",
                        description="Test Description"
                    )
            
            # Verify the call was made with correct payload
            call_args = mock_post.call_args
            assert call_args[1]['json']['fields']['project']['key'] == "DTS"
            assert call_args[1]['json']['fields']['summary'] == "Test Summary"
            assert call_args[1]['json']['fields']['description']['type'] == "doc"
            assert call_args[1]['json']['fields']['issuetype']['name'] == "Task"
    
    @pytest.mark.asyncio
    async def test_close(self, jira_client):
        """Test close method"""
        jira_client._http_client.close = AsyncMock()
        await jira_client.close()
        jira_client._http_client.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_with_no_client(self):
        """Test close when http_client is None"""
        client = JiraClient(
            base_url="https://test.atlassian.net",
            user_email="test@example.com",
            api_token="token"
        )
        client._http_client = None
        # Should not raise exception
        await client.close()

