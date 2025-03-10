from app.im.mattermost.mattermost_application import MattermostApplication
from app.im.slack.slack_application import SlackApplication
from app.im.telegram.telegram_application import TelegramApplication


def get_application(app_config, channels, default_channel):
    app_type = app_config['type']
    if app_type == 'slack':
        return SlackApplication(app_config, channels, default_channel)
    elif app_type == 'mattermost':
        return MattermostApplication(app_config, channels, default_channel)
    elif app_type == 'telegram':
        return TelegramApplication(app_config, channels, default_channel)
    else:
        raise ValueError(f'Unknown application type: {app_type}')
