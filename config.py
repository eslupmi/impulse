"""
Impulse Configuration Module

This module provides backward-compatible access to both environment and application configuration.
Environment configuration (secrets, paths, etc.) is loaded from environment variables.
Application configuration (business logic) is loaded from YAML files and validated.
"""

from app.config.config import get_config

# Load the unified configuration
config = get_config()

# Legacy environment variables (for backward compatibility)
slack_bot_user_oauth_token = config.slack_bot_user_oauth_token
slack_verification_token = config.slack_verification_token
mattermost_access_token = config.mattermost_access_token
telegram_bot_token = config.telegram_bot_token
data_path = config.data_path
config_path = config.config_path
provider_sync_interval = config.provider_sync_interval
provider_max_events = config.provider_max_events
provider_days_to_sync = config.provider_days_to_sync
provider_service_account_file = config.provider_service_account_file
cors_allowed_origins = config.cors_allowed_origins
incidents_path = config.incidents_path

# Legacy application configuration (for backward compatibility)
settings = config.settings
incident = config.incident
experimental = config.experimental
application = config.application
ui_config = config.ui_config

# Constants
INCIDENT_ACTUAL_VERSION = config.INCIDENT_ACTUAL_VERSION
check_updates = config.check_updates
