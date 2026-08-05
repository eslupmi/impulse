"""Jira integration for task creation from incidents"""
from datetime import datetime, timezone

from app.config.config import get_config
from app.integrations.jira_client import JiraClient
from app.jinja_template import JinjaTemplate
from app.logging import logger
from app.queue.constants import QueueItemType


class JiraIntegration:
    """
    High-level Jira integration logic for creating tasks from incidents.
    """

    def __init__(self, jira_client: JiraClient, tm_type: str = "jira"):
        self.jira_client = jira_client
        self.tm_type = tm_type

    @staticmethod
    def _get_project_key() -> str:
        config = get_config()
        if config.app.task_management:
            return config.app.task_management.project_key
        raise ValueError("Task management not configured")
    
    ### PRIVATE METHODS ###

    def _read_template(self, file_key: str) -> JinjaTemplate:
        """Read template file from current config"""
        config = get_config()
        default_path = f'./templates/{self.tm_type}_{file_key}.j2'
        
        if config.app.task_management and config.app.task_management.template_files:
            template_files = config.app.task_management.template_files
            if file_key == 'summary' and template_files.summary:
                file_path = template_files.summary
            elif file_key == 'description' and template_files.description:
                file_path = template_files.description
            else:
                file_path = default_path
        else:
            file_path = default_path
        
        return JinjaTemplate(open(file_path).read())

    def format_incident_for_jira(self, incident) -> tuple[str, str]:
        """
        Format incident data for Jira issue creation using templates.
        
        Args:
            incident: Incident object
        
        Returns:
            Tuple of (summary, description) for Jira issue
        """
        summary_template = self._read_template('summary')
        description_template = self._read_template('description')
        
        summary = summary_template.render(incident=incident).strip()
        description = description_template.render(incident=incident).strip()

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
            logger.debug(f"Incident {incident.uniq_id} already has Jira task: {incident.task_link}")
            return {"success": True, "message": "Task already exists"}

        if incident.task_creation_in_progress:
            logger.debug(f"Incident {incident.uniq_id} task creation already in progress")
            return {"success": True, "message": "Task creation in progress"}

        incident.task_creation_in_progress = True

        summary, description = self.format_incident_for_jira(incident)

        logger.info(f"Creating Jira task for incident {incident.uniq_id}")
        project_key = self._get_project_key()
        result = await self.jira_client.create_issue(
            project_key=project_key,
            summary=summary,
            description=description
        )

        if result:
            incident.task_link = result["url"]
            incident.dump()
            logger.info(f"Created Jira task {result['key']} for incident {incident.uniq_id}")
            response = {
                "success": True,
                "message": f"Created Jira task: {result['key']}",
                "task_key": result['key'],
                "task_url": result['url']
            }
        else:
            logger.error(f"Failed to create Jira task for incident {incident.uniq_id}")
            response = {
                "success": False,
                "message": "Failed to create Jira task"
            }

        incident.task_creation_in_progress = False
        await queue_.put(
            datetime_=datetime.now(timezone.utc),
            type_=QueueItemType.UPDATE_MESSAGE,
            uniq_id=incident.uniq_id,
            identifier=None,
            data=None
        )

        return response
