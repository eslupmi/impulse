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

# Backward-compatible exports for Grafana Renderer and JWT (used by telegram renderer code)
_renderer = settings.get('grafana_renderer', {}) or {}
# Renderer core
grafana_renderer_url = _renderer.get('renderer_url', 'http://renderer:8081')
grafana_url = _renderer.get('grafana_url', 'http://grafana:3000')
grafana_render_key = _renderer.get('render_key')
grafana_render_enabled = bool(_renderer.get('enabled', False))
grafana_render_rate_limit = int(_renderer.get('rate_limit', 60))
grafana_render_max_size = int(_renderer.get('max_size', 10 * 1024 * 1024))
grafana_render_time_to_render = int(_renderer.get('time_to_render', 15))
# Panel variables limits
panel_variables_max_values_per_var = int(_renderer.get('panel_variables_max_values_per_var', 20))
panel_variables_max_url_length = int(_renderer.get('panel_variables_max_url_length', 8192))
# JWT auth nested
_jwt = (_renderer.get('jwt_auth') or {})
jwt_auth_mode = _jwt.get('mode', 'internal')
jwt_auth_enabled = bool(_jwt.get('enabled', False))
jwt_auth_keys_dir = _jwt.get('keys_dir', f"{data_path}/jwt")
jwt_auth_kid = _jwt.get('kid', 'impulse-key-1')
jwt_auth_issuer = _jwt.get('issuer', 'http://localhost:5000')
jwt_auth_audience = _jwt.get('audience', 'impulse')
jwt_auth_ttl_seconds = int(_jwt.get('ttl_seconds', 300))
jwt_auth_rotation_enabled = bool(_jwt.get('rotation_enabled', False))
jwt_auth_rotation_interval_days = int(_jwt.get('rotation_interval_days', 120))
jwt_auth_grace_period_seconds = int(_jwt.get('grace_period_seconds', 900))
jwt_auth_max_keys = int(_jwt.get('max_keys', 3))
# External JWT
_ext = (_jwt.get('external_jwt') or {})
external_jwt_env_var_name = _ext.get('env_var_name', 'GRAFANA_JWT_TOKEN')
external_jwt_http_url = _ext.get('http_url')
external_jwt_http_method = _ext.get('http_method', 'GET')
external_jwt_http_headers = _ext.get('http_headers')
external_jwt_http_body = _ext.get('http_body')
external_jwt_http_token_json_path = _ext.get('http_token_json_path', 'access_token')
external_jwt_http_cache_ttl_seconds = int(_ext.get('http_cache_ttl_seconds', 240))
external_jwt_http_timeout_seconds = int(_ext.get('http_timeout_seconds', 10))
external_jwt_http_retries = int(_ext.get('http_retries', 2))
external_jwt_http_retry_backoff_ms = int(_ext.get('http_retry_backoff_ms', 300))
external_jwt_clock_skew_seconds = int(_ext.get('clock_skew_seconds', 15))
external_jwt_allow_fallback_to_disabled = bool(_ext.get('allow_fallback_to_disabled', False))
