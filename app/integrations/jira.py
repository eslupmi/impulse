"""Jira integration for task creation from incidents"""
import base64
from datetime import datetime, timezone
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
        url = f"{self.base_url}/rest/api/3/issue"
        
        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": description
                                }
                            ]
                        }
                    ]
                },
                "issuetype": {"name": "Task"}
            }
        }
        
        try:
            async with self._http_client:
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


class JiraIntegration:
    """
    High-level Jira integration logic for creating tasks from incidents.
    """
    
    def __init__(self, jira_client: JiraClient, project_key: str):
        """
        Initialize Jira integration.
        
        Args:
            jira_client: JiraClient instance
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
        description_parts.append(f"Incident Status: {incident.status}")
        
        if incident.assigned_fullname:
            description_parts.append(f"Assigned to: {incident.assigned_fullname}")
        
        # Add alerts count
        alerts_count = len(payload.get('alerts', []))
        description_parts.append(f"Alerts Count: {alerts_count}")
        
        # Add IM thread link
        if incident.link:
            description_parts.append(f"IM Thread: {incident.link}")
        
        # Add group labels if present
        if group_labels:
            description_parts.append("\nGroup Labels:")
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
            await queue_.put(
                datetime_=datetime.now(timezone.utc),
                type_='update_status',
                incident_uuid=incident.uuid,
                identifier=None,
                data=None
            )
            
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
