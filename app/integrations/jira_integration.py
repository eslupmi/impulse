"""Jira integration for task creation from incidents"""
from datetime import datetime, timezone

from app.integrations.jira_client import JiraClient
from app.logging import logger
from app.jinja_template import JinjaTemplate, jira_summary_template, jira_description_template


class JiraIntegration:
    """
    High-level Jira integration logic for creating tasks from incidents.
    """
    
    def __init__(self, jira_client: JiraClient, project_key: str,
                 summary_template: str = None, description_template: str = None):
        """
        Initialize Jira integration.
        
        Args:
            jira_client: JiraClient instance
            project_key: Default Jira project key for task creation
            summary_template: Optional custom Jinja template for issue summary
            description_template: Optional custom Jinja template for issue description
        """
        self.jira_client = jira_client
        self.project_key = project_key
        
        # Initialize templates
        self.summary_template = JinjaTemplate(summary_template or jira_summary_template)
        self.description_template = JinjaTemplate(description_template or jira_description_template)
    
    def format_incident_for_jira(self, incident) -> tuple[str, str]:
        """
        Format incident data for Jira issue creation using templates.
        
        Args:
            incident: Incident object
        
        Returns:
            Tuple of (summary, description) for Jira issue
        """
        # Render summary from template
        summary = self.summary_template.render(incident=incident).strip()
        
        # Render description from template
        description = self.description_template.render(incident=incident).strip()
        
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

