"""Jira integration for task creation from incidents"""
from datetime import datetime, timezone
from typing import Optional

from app.integrations.jira_client import JiraClient
from app.jinja_template import JinjaTemplate, load_template_file
from app.logging import logger


class JiraIntegration:
    """
    High-level Jira integration logic for creating tasks from incidents.
    """

    def __init__(self, jira_client: JiraClient, project_key: str, 
                 tm_type: str = "jira",
                 template_files: Optional[dict] = None):
        """
        Initialize Jira integration.
        
        Args:
            jira_client: JiraClient instance
            project_key: Default Jira project key for task creation
            tm_type: Task management type (e.g., "jira") - used for default template paths
            template_files: Optional dict with 'summary' and 'description' template paths
        """
        self.jira_client = jira_client
        self.project_key = project_key
        
        def read_template(file_key: str, default_path: str) -> JinjaTemplate:
            """Read template file, using config path if provided, otherwise default"""
            if template_files and template_files.get(file_key):
                file_path = template_files.get(file_key)
                # Use default if path is empty string
                if not file_path:
                    file_path = default_path
            else:
                file_path = default_path
            return JinjaTemplate(open(file_path).read())
        
        # Use tm_type to determine default template paths
        default_summary = f'./templates/{tm_type}_summary.j2'
        default_description = f'./templates/{tm_type}_description.j2'
        
        self.summary_template = read_template('summary', default_summary)
        self.description_template = read_template('description', default_description)

    def format_incident_for_jira(self, incident) -> tuple[str, str]:
        """
        Format incident data for Jira issue creation using templates.
        
        Args:
            incident: Incident object
        
        Returns:
            Tuple of (summary, description) for Jira issue
        """
        summary = self.summary_template.render(incident=incident).strip()
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
        if incident.task_link:
            logger.debug(f"Incident {incident.uuid} already has Jira task: {incident.task_link}")
            return {"success": True, "message": "Task already exists"}

        if incident.task_creation_in_progress:
            logger.debug(f"Incident {incident.uuid} task creation already in progress")
            return {"success": True, "message": "Task creation in progress"}

        incident.task_creation_in_progress = True

        summary, description = self.format_incident_for_jira(incident)

        logger.info(f"Creating Jira task for incident {incident.uuid}")
        result = await self.jira_client.create_issue(
            project_key=self.project_key,
            summary=summary,
            description=description
        )

        if result:
            incident.task_link = result["url"]
            incident.dump()
            logger.info(f"Created Jira task {result['key']} for incident {incident.uuid}")
            response = {
                "success": True,
                "message": f"Created Jira task: {result['key']}",
                "task_key": result['key'],
                "task_url": result['url']
            }
        else:
            logger.error(f"Failed to create Jira task for incident {incident.uuid}")
            response = {
                "success": False,
                "message": "Failed to create Jira task"
            }

        incident.task_creation_in_progress = False
        await queue_.put(
            datetime_=datetime.now(timezone.utc),
            type_='update_message',
            incident_uuid=incident.uuid,
            identifier=None,
            data=None
        )

        return response
