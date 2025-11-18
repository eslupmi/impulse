from app.im.mattermost.mattermost_application import MattermostApplication
from app.im.slack.slack_application import SlackApplication
from app.im.telegram.telegram_application import TelegramApplication
from app.im.null.null_application import NullApplication
from app.config.validation import ApplicationConfig
from app.config.environment import get_environment_config
from app.logging import logger


def get_application(app_config: ApplicationConfig, channels, default_channel):
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
    
    # Initialize Jira integration if enabled
    env_config = get_environment_config()
    if env_config.jira_enabled:
        from app.integrations.jira import JiraClient, JiraIntegration
        logger.info("Initializing Jira integration with Basic Auth...")
        jira_client = JiraClient(
            base_url=env_config.jira_base_url,
            user_email=env_config.jira_user_email,
            api_token=env_config.jira_api_token
        )
        messenger.jira_integration = JiraIntegration(jira_client, env_config.jira_project_key)
        logger.info("Jira integration initialized and ready.")
    
    return messenger
