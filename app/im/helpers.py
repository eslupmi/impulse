from typing import Optional

from app.config.environment import EnvironmentConfig, get_environment_config
from app.config.validation import ApplicationConfig, TaskManagementConfig
from app.im.application import Application
from app.im.mattermost.mattermost_application import MattermostApplication
from app.im.null.null_application import NullApplication
from app.im.slack.slack_application import SlackApplication
from app.im.telegram.telegram_application import TelegramApplication
from app.integrations.jira_client import JiraClient
from app.integrations.jira_integration import JiraIntegration
from app.logging import logger


def create_task_management_integration(
    task_management_config: TaskManagementConfig,
    env_config: EnvironmentConfig
) -> JiraIntegration:
    """
    Create and configure JiraIntegration instance.
    
    Args:
        task_management_config: Task management configuration
        env_config: Environment configuration with Jira credentials
        
    Returns:
        Configured JiraIntegration instance
    """
    jira_client = JiraClient(
        base_url=env_config.jira_base_url,
        user_email=env_config.jira_user_email,
        api_token=env_config.jira_api_token
    )
    
    return JiraIntegration(jira_client, tm_type=task_management_config.type.value)


def get_application(app_config: ApplicationConfig, channels, default_channel,
                   task_management_config: Optional[TaskManagementConfig] = None):
    app_type = app_config.type
    if app_type == 'slack':
        messenger = SlackApplication(app_config, channels, default_channel)
    elif app_type == 'mattermost':
        messenger = MattermostApplication(app_config, channels, default_channel)
    elif app_type == 'telegram':
        messenger = TelegramApplication(app_config, channels, default_channel)
    elif app_type == 'none':
        messenger = NullApplication(app_config, channels, default_channel)
    else:
        raise ValueError(f'Unknown application type: {app_type}')
    
    if task_management_config:
        initialize_task_management_integration(messenger, task_management_config)
    
    return messenger


def initialize_task_management_integration(
    messenger: Application,
    task_management_config: TaskManagementConfig
) -> None:
    """
    Initialize task management integration for the messenger.
    
    Args:
        messenger: Application instance to attach integration to
        task_management_config: Task management configuration
    """
    env_config = get_environment_config()
    provider = task_management_config.type.value
    if not env_config.task_management_enabled:
        logger.warning("Task management is configured but ENVs are not set", extra={'provider': provider})
        return
    
    if task_management_config.type.value == "jira":
        logger.info("Initializing task management", extra={'provider': provider})
        messenger.task_management_integration = create_task_management_integration(
            task_management_config,
            env_config
        )
        logger.info("Task management initialized and ready", extra={'provider': provider})
