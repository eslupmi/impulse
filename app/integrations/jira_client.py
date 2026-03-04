"""Jira Cloud API client with Basic Authentication"""
import base64
from typing import Dict, Optional

from app.http_client.rate_limited_client import RateLimitedClient
from app.logging import logger


class JiraClient:
    """
    Jira Cloud API client with Basic Authentication.
    Uses email + API token for server-to-server authentication.
    """
    
    def __init__(
        self,
        base_url: str,
        user_email: str,
        api_token: str
    ):
        """
        Initialize Jira client with Basic Auth credentials.
        
        Args:
            base_url: Jira base URL (e.g., https://your-domain.atlassian.net)
            user_email: User email for authentication
            api_token: API token for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.user_email = user_email
        self.api_token = api_token
        
        # Create Basic Auth token: base64("email:token")
        credentials = f"{user_email}:{api_token}"
        self._auth_token = base64.b64encode(credentials.encode()).decode('ascii')
        
        # Create dedicated HTTP client for Jira API
        self._http_client = RateLimitedClient(
            rate_limit=None,  # Jira has its own rate limiting
            retry_attempts=3,
            timeout=30.0
        )
    
    ### private methods ###
    def _get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for Jira API requests.
        
        Returns:
            Dict with Authorization, Content-Type, and Accept headers
        """
        return {
            "Authorization": f"Basic {self._auth_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    async def create_issue(
        self,
        project_key: str,
        summary: str,
        description: str
    ) -> Optional[Dict]:
        """
        Create a Jira issue using REST API v3.
        
        Args:
            project_key: Jira project key (e.g., "DTS")
            summary: Issue summary/title
            description: Issue description
        
        Returns:
            Dict with 'key' and 'url' if successful, None otherwise
        """
        url = f"{self.base_url}/rest/api/2/issue"
        
        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": description,
                "issuetype": {"name": "Task"}
            }
        }
        
        try:
            self._http_client.initialize_client()
            response = await self._http_client.post(
                url,
                json=payload,
                headers=self._get_auth_headers()
            )
            
            if response.status == 201:
                data = await response.json()
                issue_key = data.get("key")
                # Build browse URL from key
                issue_url = f"{self.base_url}/browse/{issue_key}"
                
                logger.info(f"Successfully created Jira issue: {issue_key}")
                return {
                    "key": issue_key,
                    "url": issue_url
                }
            else:
                error_text = await response.text()
                logger.error(f"Failed to create Jira issue: {response.status} - {error_text}")
                return None
        except Exception as e:
            logger.error(f"Error creating Jira issue: {e}")
            return None
    
    async def close(self):
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.close()

