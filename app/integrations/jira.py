"""Jira integration for task creation from incidents"""
import asyncio
import hashlib
import hmac
import secrets
import time
from abc import ABC, abstractmethod
from base64 import b64encode
from typing import Dict, Optional
from urllib.parse import urlencode, quote

from app.http_client.rate_limited_client import RateLimitedClient
from app.logging import logger


class JiraClientBase(ABC):
    """
    Abstract base class for Jira API clients.
    Implementations handle OAuth for Cloud (2.0) and Server (1.0a).
    """
    
    def __init__(self, base_url: str, redirect_uri: str):
        """
        Initialize base Jira client.
        
        Args:
            base_url: Jira API base URL
            redirect_uri: OAuth redirect URI
        """
        self._base_url = base_url
        self.redirect_uri = redirect_uri
        
        # Create dedicated HTTP client for Jira API
        self._http_client = RateLimitedClient(
            rate_limit=None,  # Jira has its own rate limiting
            retry_attempts=3,
            timeout=30.0
        )
    
    @abstractmethod
    def get_authorization_url(self) -> str:
        """Generate OAuth authorization URL."""
        pass
    
    @abstractmethod
    async def exchange_code_for_token(self, code: str, state: str) -> bool:
        """Exchange authorization code for access token."""
        pass
    
    @abstractmethod
    def is_authenticated(self) -> bool:
        """Check if client has a valid access token."""
        pass
    
    @abstractmethod
    async def _get_auth_headers(self, method: str, url: str) -> Dict[str, str]:
        """Get authentication headers for API request."""
        pass
    
    async def create_issue(
        self,
        project_key: str,
        summary: str,
        description: str
    ) -> Optional[Dict]:
        """
        Create a Jira issue.
        
        Args:
            project_key: Jira project key (e.g., "DTS")
            summary: Issue summary/title
            description: Issue description
        
        Returns:
            Dict with 'key' and 'url' if successful, None otherwise
        """
        url = f"{self._base_url}/issue"
        
        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": description,
                "issuetype": {"name": "Task"}
            }
        }
        
        try:
            async with self._http_client:
                headers = await self._get_auth_headers("POST", url)
                headers["Content-Type"] = "application/json"
                headers["Accept"] = "application/json"
                
                response = await self._http_client.post(
                    url,
                    json=payload,
                    headers=headers
                )
                
                if response.status == 201:
                    data = await response.json()
                    issue_key = data.get("key")
                    issue_url = data.get("self", "").replace("/rest/api/2/issue/", "/browse/")
                    
                    logger.info(f"Successfully created Jira issue: {issue_key}")
                    return {
                        "key": issue_key,
                        "url": issue_url
                    }
                elif response.status == 401:
                    # Try refreshing token and retry
                    logger.warning("Jira API returned 401, attempting token refresh...")
                    if await self._refresh_access_token():
                        # Retry with new token
                        return await self.create_issue(project_key, summary, description)
                    else:
                        logger.error("Failed to refresh Jira access token")
                        return None
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to create Jira issue: {response.status} - {error_text}")
                    return None
        except Exception as e:
            logger.error(f"Error creating Jira issue: {e}")
            return None
    
    async def _refresh_access_token(self) -> bool:
        """Refresh the access token. Override in subclasses if supported."""
        return False
    
    async def close(self):
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.close()


class JiraCloudClient(JiraClientBase):
    """
    Jira Cloud API client using OAuth 2.0.
    """
    
    # OAuth URLs for Jira Cloud
    OAUTH_AUTHORIZE_URL = "https://auth.atlassian.com/authorize"
    OAUTH_TOKEN_URL = "https://auth.atlassian.com/oauth/token"
    OAUTH_AUDIENCE = "api.atlassian.com"
    OAUTH_SCOPES = "read:jira-work write:jira-work read:jira-user"
    
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        cloud_id: str,
        redirect_uri: str,
        access_token: Optional[str] = None
    ):
        """
        Initialize Jira Cloud client.
        
        Args:
            client_id: OAuth client ID
            client_secret: OAuth client secret
            cloud_id: Jira cloud instance ID
            redirect_uri: OAuth redirect URI
            access_token: Initial access token (optional)
        """
        base_url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/2"
        super().__init__(base_url, redirect_uri)
        
        self.client_id = client_id
        self.client_secret = client_secret
        self.cloud_id = cloud_id
        
        # Store tokens in memory
        self._access_token = access_token
        self._refresh_token: Optional[str] = None
        
        # Store OAuth state for CSRF protection
        self._oauth_state: Optional[str] = None
    
    def get_authorization_url(self) -> str:
        """Generate OAuth 2.0 authorization URL."""
        # Generate and store state for CSRF protection
        self._oauth_state = secrets.token_urlsafe(32)
        
        params = {
            "audience": self.OAUTH_AUDIENCE,
            "client_id": self.client_id,
            "scope": self.OAUTH_SCOPES,
            "redirect_uri": self.redirect_uri,
            "state": self._oauth_state,
            "response_type": "code",
            "prompt": "consent"
        }
        
        return f"{self.OAUTH_AUTHORIZE_URL}?{urlencode(params)}"
    
    async def exchange_code_for_token(self, code: str, state: str) -> bool:
        """Exchange authorization code for access token."""
        # Validate state to prevent CSRF attacks
        if state != self._oauth_state:
            logger.error("OAuth state mismatch - possible CSRF attack")
            return False
        
        payload = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri
        }
        
        try:
            async with self._http_client:
                response = await self._http_client.post(
                    self.OAUTH_TOKEN_URL,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status == 200:
                    data = await response.json()
                    self._access_token = data.get("access_token")
                    self._refresh_token = data.get("refresh_token")
                    logger.info("Successfully obtained access token via OAuth 2.0")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to exchange code for token: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"Error exchanging code for token: {e}")
            return False
    
    def is_authenticated(self) -> bool:
        """Check if client has a valid access token."""
        return self._access_token is not None
    
    async def _get_auth_headers(self, method: str, url: str) -> Dict[str, str]:
        """Get OAuth 2.0 authentication headers."""
        return {"Authorization": f"Bearer {self._access_token}"}
    
    async def _refresh_access_token(self) -> bool:
        """Refresh the access token using the refresh token."""
        if not self._refresh_token:
            logger.error("No refresh token available to refresh access token")
            return False
        
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self._refresh_token
        }
        
        try:
            async with self._http_client:
                response = await self._http_client.post(
                    self.OAUTH_TOKEN_URL,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status == 200:
                    data = await response.json()
                    self._access_token = data.get("access_token")
                    # Update refresh token if provided
                    if "refresh_token" in data:
                        self._refresh_token = data.get("refresh_token")
                    logger.info("Successfully refreshed Jira access token")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to refresh access token: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"Error refreshing access token: {e}")
            return False


class JiraServerClient(JiraClientBase):
    """
    Jira Server/Data Center API client using OAuth 1.0a.
    """
    
    def __init__(
        self,
        base_url: str,
        consumer_key: str,
        private_key: str,
        redirect_uri: str
    ):
        """
        Initialize Jira Server client.
        
        Args:
            base_url: Jira server base URL (e.g., https://jira.company.com)
            consumer_key: OAuth consumer key
            private_key: RSA private key in PKCS8 format
            redirect_uri: OAuth redirect URI
        """
        api_base_url = f"{base_url.rstrip('/')}/rest/api/2"
        super().__init__(api_base_url, redirect_uri)
        
        self.base_url = base_url
        self.consumer_key = consumer_key
        self.private_key = private_key
        
        # OAuth 1.0a tokens
        self._request_token: Optional[str] = None
        self._request_token_secret: Optional[str] = None
        self._access_token: Optional[str] = None
        self._access_token_secret: Optional[str] = None
        self._oauth_verifier: Optional[str] = None
        
        # OAuth state for CSRF protection
        self._oauth_state: Optional[str] = None
    
    def get_authorization_url(self) -> str:
        """
        Generate OAuth 1.0a authorization URL.
        Note: This is a simplified version. Full OAuth 1.0a with RSA signing
        requires additional libraries like `requests-oauthlib` or manual implementation.
        """
        # Generate state for CSRF protection
        self._oauth_state = secrets.token_urlsafe(32)
        
        # For OAuth 1.0a, we need to:
        # 1. Get request token (requires RSA signing)
        # 2. Return authorization URL with request token
        
        # This is a placeholder - actual implementation requires RSA signing
        logger.warning("OAuth 1.0a for Jira Server requires additional implementation with RSA signing")
        
        return f"{self.base_url}/plugins/servlet/oauth/authorize?oauth_token=PLACEHOLDER&state={self._oauth_state}"
    
    async def exchange_code_for_token(self, code: str, state: str) -> bool:
        """
        Exchange OAuth verifier for access token.
        Note: OAuth 1.0a uses 'oauth_verifier' instead of 'code'.
        """
        # Validate state to prevent CSRF attacks
        if state != self._oauth_state:
            logger.error("OAuth state mismatch - possible CSRF attack")
            return False
        
        # This requires RSA signing and OAuth 1.0a protocol
        logger.warning("OAuth 1.0a token exchange requires additional implementation with RSA signing")
        
        # Placeholder for OAuth 1.0a implementation
        return False
    
    def is_authenticated(self) -> bool:
        """Check if client has a valid access token."""
        return self._access_token is not None
    
    async def _get_auth_headers(self, method: str, url: str) -> Dict[str, str]:
        """
        Get OAuth 1.0a authentication headers.
        Requires RSA-SHA1 signature.
        """
        if not self.is_authenticated():
            return {}
        
        # OAuth 1.0a requires complex signature generation
        # This is a placeholder - actual implementation requires:
        # 1. Generate OAuth parameters (nonce, timestamp, etc.)
        # 2. Create signature base string
        # 3. Sign with RSA private key
        # 4. Build Authorization header
        
        logger.warning("OAuth 1.0a header generation requires additional implementation with RSA signing")
        
        return {
            "Authorization": f"OAuth oauth_token={self._access_token}"
        }


def create_jira_client(config) -> JiraClientBase:
    """
    Factory function to create appropriate Jira client based on configuration.
    
    Args:
        config: Environment configuration object
    
    Returns:
        JiraCloudClient or JiraServerClient
    """
    jira_type = config.jira_type.lower()
    
    if jira_type == 'cloud':
        logger.info("Creating Jira Cloud client (OAuth 2.0)")
        return JiraCloudClient(
            client_id=config.jira_client_id,
            client_secret=config.jira_client_secret,
            cloud_id=config.jira_cloud_id,
            redirect_uri=config.jira_redirect_uri
        )
    elif jira_type == 'server':
        logger.info("Creating Jira Server client (OAuth 1.0a)")
        return JiraServerClient(
            base_url=config.jira_base_url,
            consumer_key=config.jira_consumer_key,
            private_key=config.jira_private_key,
            redirect_uri=config.jira_redirect_uri
        )
    else:
        raise ValueError(f"Unknown Jira type: {jira_type}. Must be 'cloud' or 'server'.")


class JiraIntegration:
    """
    High-level Jira integration logic for creating tasks from incidents.
    """
    
    def __init__(self, jira_client: JiraClientBase, project_key: str):
        """
        Initialize Jira integration.
        
        Args:
            jira_client: JiraClientBase instance (Cloud or Server)
            project_key: Default Jira project key for task creation
        """
        self.jira_client = jira_client
        self.project_key = project_key
    
    def format_incident_for_jira(self, incident) -> tuple[str, str]:
        """
        Format incident data for Jira issue creation.
        
        Args:
            incident: Incident object
        
        Returns:
            Tuple of (summary, description) for Jira issue
        """
        # Extract summary from groupLabels or first alert
        payload = incident.payload
        group_labels = payload.get('groupLabels', {})
        
        # Try to build a meaningful summary
        if group_labels:
            # Use group labels to build summary
            summary_parts = []
            for key, value in group_labels.items():
                summary_parts.append(f"{key}={value}")
            summary = "Alert: " + ", ".join(summary_parts)
        else:
            # Fallback to first alert's alertname
            alerts = payload.get('alerts', [])
            if alerts:
                first_alert = alerts[0]
                labels = first_alert.get('labels', {})
                alertname = labels.get('alertname', 'Unknown Alert')
                summary = f"Alert: {alertname}"
            else:
                summary = "Incident Alert"
        
        # Truncate summary if too long (Jira has 255 char limit)
        if len(summary) > 255:
            summary = summary[:252] + "..."
        
        # Build description with incident details
        description_parts = []
        description_parts.append(f"*Incident Status:* {incident.status}")
        
        if incident.assigned_fullname:
            description_parts.append(f"*Assigned to:* {incident.assigned_fullname}")
        
        # Add alerts count
        alerts_count = len(payload.get('alerts', []))
        description_parts.append(f"*Alerts Count:* {alerts_count}")
        
        # Add IM thread link
        if incident.permalink:
            description_parts.append(f"*IM Thread:* {incident.permalink}")
        
        # Add group labels if present
        if group_labels:
            description_parts.append("\n*Group Labels:*")
            for key, value in group_labels.items():
                # Truncate long values
                if len(str(value)) > 200:
                    value = str(value)[:197] + "..."
                description_parts.append(f"- {key}: {value}")
        
        description = "\n".join(description_parts)
        
        return summary, description
    
    async def handle_button_press(self, incident, queue_):
        """
        Handle Jira button press for an incident.
        
        Args:
            incident: Incident object
            queue_: Queue manager
        
        Returns:
            Response dict with success status
        """
        # Check if Jira is authenticated
        if not self.jira_client.is_authenticated():
            logger.warning(f"Jira button pressed but not authenticated. Incident: {incident.uuid}")
            return {
                "success": False,
                "message": "Jira is not authenticated. Please authorize the application first."
            }
        
        # If task already exists, do nothing (button acts as link)
        if incident.task_link:
            logger.debug(f"Incident {incident.uuid} already has Jira task: {incident.task_link}")
            return {"success": True, "message": "Task already exists"}
        
        # Create Jira task
        summary, description = self.format_incident_for_jira(incident)
        
        logger.info(f"Creating Jira task for incident {incident.uuid}")
        result = await self.jira_client.create_issue(
            project_key=self.project_key,
            summary=summary,
            description=description
        )
        
        if result:
            # Update incident with task link
            incident.task_link = result["url"]
            incident.dump()
            
            # Add update_status queue item to update the thread and show message
            from app.queue.queue import QueueItem
            queue_item = QueueItem(
                incident_uuid=incident.uuid,
                type_='update_status',
                datetime_=None,
                identifier=None
            )
            await queue_.put(queue_item)
            
            logger.info(f"Created Jira task {result['key']} for incident {incident.uuid}")
            return {
                "success": True,
                "message": f"Created Jira task: {result['key']}",
                "task_key": result['key'],
                "task_url": result['url']
            }
        else:
            logger.error(f"Failed to create Jira task for incident {incident.uuid}")
            return {
                "success": False,
                "message": "Failed to create Jira task"
            }
