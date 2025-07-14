import os

from dotenv import load_dotenv

from app.logging import logger

load_dotenv()

slack_bot_user_oauth_token = os.getenv('SLACK_BOT_USER_OAUTH_TOKEN')
slack_verification_token = os.getenv('SLACK_VERIFICATION_TOKEN')
mattermost_access_token = os.getenv('MATTERMOST_ACCESS_TOKEN')
telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
data_path = os.getenv('DATA_PATH', default='./data')
config_path = os.getenv('CONFIG_PATH', default='./')
provider_sync_interval = int(os.getenv('CHAIN_PROVIDER_SYNC_INTERVAL_SECONDS', default=60))
provider_max_events = int(os.getenv('CHAIN_PROVIDER_MAX_EVENTS', default=10))
provider_days_to_sync = int(os.getenv('CHAIN_PROVIDER_DAYS_TO_SYNC', default=7))
provider_service_account_file = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', default="./key.json")

# Get CORS allowed origins from environment variable, default to localhost
cors_allowed_origins = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:5000').split(',')

incidents_path = data_path + '/incidents'
INCIDENT_ACTUAL_VERSION = 'v3.0.0'

try:
    from app.config.loader import load_and_validate_config, get_legacy_config_dict

    validated_config, raw_config = load_and_validate_config(f'{config_path}/impulse.yml')
    settings = get_legacy_config_dict(validated_config)

    # Extract sections for legacy code
    incident = settings.get('incident', {})
    experimental = settings.get('experimental', {})

    application = settings.get('application')
    ui_config = settings.get('ui', {})
except Exception as e:
    logger.error(f"Configuration validation failed: {e}\nPlease check your impulse.yml file and fix any validation errors.\nDocumentation: https://docs.impulse.bot/latest/config_file/")
    raise SystemExit(1)
