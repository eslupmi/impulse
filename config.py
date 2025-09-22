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
provider_sync_interval = int(os.getenv('CHAIN_PROVIDER_SYNC_INTERVAL_SECONDS', default=60))
provider_max_events = int(os.getenv('CHAIN_PROVIDER_MAX_EVENTS', default=10))
provider_days_to_sync = int(os.getenv('CHAIN_PROVIDER_DAYS_TO_SYNC', default=7))
provider_service_account_file = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', default="./key.json")

# Get CORS allowed origins from environment variable, default to localhost
cors_allowed_origins = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:5000').split(',')

incidents_path = data_path + '/incidents'
INCIDENT_ACTUAL_VERSION = 'v3.0.0'

with open(f'{config_path}/impulse.yml', 'r') as file:
    try:
        settings = yaml.safe_load(file)

        incident = dict()
        
        incident['timeouts'] = dict()
        incident['timeouts']['firing'] = settings.get('incident', {}).get('timeouts', {}).get('firing', '6h')
        incident['timeouts']['unknown'] = settings.get('incident', {}).get('timeouts', {}).get('unknown', '6h')
        incident['timeouts']['resolved'] = settings.get('incident', {}).get('timeouts', {}).get('resolved', '12h')

        incident['notifications'] = dict()
        incident['notifications']['assignment'] = settings.get('incident', {}).get('notifications', {}).get('assignment', True)
        incident['notifications']['new_firing'] = settings.get('incident', {}).get('notifications', {}).get('new_firing', True)
        incident['notifications']['partial_resolved'] = settings.get('incident', {}).get('notifications', {}).get('partial_resolved', False)

        experimental = settings.get('experimental', {})
        application = settings.get('application')
        ui_config = settings.get('ui', {})
    except yaml.YAMLError as e:
        print(f"Error reading YAML file: {e}")
