import os

import yaml
from dotenv import load_dotenv

load_dotenv()

slack_bot_user_oauth_token = os.getenv('SLACK_BOT_USER_OAUTH_TOKEN')
slack_verification_token = os.getenv('SLACK_VERIFICATION_TOKEN')
mattermost_access_token = os.getenv('MATTERMOST_ACCESS_TOKEN')
telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
data_path = os.getenv('DATA_PATH', default='./data')
config_path = os.getenv('CONFIG_PATH', default='./')
log_level = os.getenv('LOG_LEVEL', default='INFO')

incidents_path = data_path + '/incidents'
INCIDENT_ACTUAL_VERSION = 'v0.4'

with open(f'{config_path}/impulse.yml', 'r') as file:
    try:
        settings = yaml.safe_load(file)

        incident = dict()
        incident['alerts_firing_notifications'] = settings.get('incident', {}).get('alerts_firing_notifications', False)
        incident['alerts_resolved_notifications'] = settings.get('incident', {}).get('alerts_resolved_notifications', False)
        incident['timeouts'] = dict()
        incident['timeouts']['firing'] = settings.get('incident', {}).get('timeouts', {}).get('firing', '6h')
        incident['timeouts']['unknown'] = settings.get('incident', {}).get('timeouts', {}).get('unknown', '6h')
        incident['timeouts']['resolved'] = settings.get('incident', {}).get('timeouts', {}).get('resolved', '12h')

        experimental = settings.get('experimental', {})
        check_updates = True
        application = settings.get('application')
    except yaml.YAMLError as e:
        print(f"Error reading YAML file: {e}")
