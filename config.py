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

# Grafana Renderer configuration - будет переопределено из impulse.yml
grafana_renderer_url = os.getenv('GRAFANA_RENDERER_URL', default='http://renderer:8081')
grafana_url = os.getenv('GRAFANA_URL', default='http://grafana:3000')
grafana_render_key = os.getenv('GRAFANA_RENDER_KEY', default=None)
grafana_render_enabled = os.getenv('GRAFANA_RENDER_ENABLED', default='false').lower() == 'true'
grafana_render_rate_limit = int(os.getenv('GRAFANA_RENDER_RATE_LIMIT', default='60'))  # секунды
grafana_render_max_size = int(os.getenv('GRAFANA_RENDER_MAX_SIZE', default='10485760'))  # 10MB в байтах
grafana_render_time_to_render = int(os.getenv('GRAFANA_RENDER_TIME_TO_RENDER', default='15'))  # минуты

# JWT auth configuration for Grafana (auth.jwt) under grafana_renderer.jwt_auth
# Mode: disabled | internal | external_env | external_http
jwt_auth_mode = os.getenv('GRAFANA_RENDERER_JWT_AUTH_MODE', default='internal')
jwt_auth_enabled = os.getenv('GRAFANA_RENDERER_JWT_AUTH_ENABLED', default='false').lower() == 'true'
jwt_auth_keys_dir = os.getenv('GRAFANA_RENDERER_JWT_AUTH_KEYS_DIR', default=os.path.join(data_path, 'jwt'))
jwt_auth_kid = os.getenv('GRAFANA_RENDERER_JWT_AUTH_KID', default='impulse-key-1')
jwt_auth_issuer = os.getenv('GRAFANA_RENDERER_JWT_AUTH_ISSUER', default='http://localhost:5000')
jwt_auth_audience = os.getenv('GRAFANA_RENDERER_JWT_AUTH_AUDIENCE', default='impulse')
jwt_auth_ttl_seconds = int(os.getenv('GRAFANA_RENDERER_JWT_AUTH_TTL_SECONDS', default='300'))
jwt_auth_rotation_enabled = os.getenv('GRAFANA_RENDERER_JWT_AUTH_ROTATION_ENABLED', default='false').lower() == 'true'
jwt_auth_rotation_interval_days = int(os.getenv('GRAFANA_RENDERER_JWT_AUTH_ROTATION_INTERVAL_DAYS', default='120'))
jwt_auth_grace_period_seconds = int(os.getenv('GRAFANA_RENDERER_JWT_AUTH_GRACE_PERIOD_SECONDS', default='900'))
jwt_auth_max_keys = int(os.getenv('GRAFANA_RENDERER_JWT_AUTH_MAX_KEYS', default='3'))

# External JWT provider configuration
external_jwt_env_var_name = os.getenv('GRAFANA_RENDERER_EXTERNAL_JWT_ENV_VAR_NAME', default='GRAFANA_JWT_TOKEN')
external_jwt_http_url = os.getenv('GRAFANA_RENDERER_EXTERNAL_JWT_HTTP_URL')
external_jwt_http_method = os.getenv('GRAFANA_RENDERER_EXTERNAL_JWT_HTTP_METHOD', default='GET')
external_jwt_http_headers = os.getenv('GRAFANA_RENDERER_EXTERNAL_JWT_HTTP_HEADERS')  # JSON-строка
external_jwt_http_body = os.getenv('GRAFANA_RENDERER_EXTERNAL_JWT_HTTP_BODY')  # JSON-строка
external_jwt_http_token_json_path = os.getenv('GRAFANA_RENDERER_EXTERNAL_JWT_HTTP_TOKEN_JSON_PATH', default='access_token')
external_jwt_http_cache_ttl_seconds = int(os.getenv('GRAFANA_RENDERER_EXTERNAL_JWT_HTTP_CACHE_TTL_SECONDS', default='240'))
external_jwt_http_timeout_seconds = int(os.getenv('GRAFANA_RENDERER_EXTERNAL_JWT_HTTP_TIMEOUT_SECONDS', default='10'))
external_jwt_http_retries = int(os.getenv('GRAFANA_RENDERER_EXTERNAL_JWT_HTTP_RETRIES', default='2'))
external_jwt_http_retry_backoff_ms = int(os.getenv('GRAFANA_RENDERER_EXTERNAL_JWT_HTTP_RETRY_BACKOFF_MS', default='300'))
external_jwt_clock_skew_seconds = int(os.getenv('GRAFANA_RENDERER_EXTERNAL_JWT_CLOCK_SKEW_SECONDS', default='15'))
external_jwt_allow_fallback_to_disabled = os.getenv('GRAFANA_RENDERER_EXTERNAL_JWT_ALLOW_FALLBACK_TO_DISABLED', default='false').lower() == 'true'

# Panel variables configuration for Grafana rendering
panel_variables_max_values_per_var = int(os.getenv('GRAFANA_RENDERER_PANEL_VARIABLES_MAX_VALUES_PER_VAR', default='20'))
panel_variables_max_url_length = int(os.getenv('GRAFANA_RENDERER_PANEL_VARIABLES_MAX_URL_LENGTH', default='8192'))

# Get CORS allowed origins from environment variable, default to localhost
cors_allowed_origins = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:5000').split(',')

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
        incident['notifications'] = dict()
        incident['notifications']['assignment'] = settings.get('incident', {}).get('notifications', {}).get('assignment', True)

        experimental = settings.get('experimental', {})
        application = settings.get('application')
        ui_config = settings.get('ui', {})
        
        # Grafana Renderer configuration from impulse.yml
        grafana_renderer_config = settings.get('grafana_renderer', {})
        if grafana_renderer_config:
            # Переопределяем значения из конфигурационного файла, если не заданы в env
            if not os.getenv('GRAFANA_RENDERER_URL'):
                grafana_renderer_url = grafana_renderer_config.get('renderer_url', grafana_renderer_url)
            if not os.getenv('GRAFANA_URL'):
                grafana_url = grafana_renderer_config.get('grafana_url', grafana_url)
            if not os.getenv('GRAFANA_RENDER_KEY'):
                grafana_render_key = grafana_renderer_config.get('render_key', grafana_render_key)
            if not os.getenv('GRAFANA_RENDER_ENABLED'):
                grafana_render_enabled = grafana_renderer_config.get('enabled', grafana_render_enabled)
            if not os.getenv('GRAFANA_RENDER_RATE_LIMIT'):
                grafana_render_rate_limit = grafana_renderer_config.get('rate_limit', grafana_render_rate_limit)
            if not os.getenv('GRAFANA_RENDER_MAX_SIZE'):
                grafana_render_max_size = grafana_renderer_config.get('max_size', grafana_render_max_size)
            if not os.getenv('GRAFANA_RENDER_TIME_TO_RENDER'):
                grafana_render_time_to_render = grafana_renderer_config.get('time_to_render', grafana_render_time_to_render)

        # JWT auth nested configuration: grafana_renderer.jwt_auth
        jwt_cfg = settings.get('grafana_renderer', {}).get('jwt_auth', {})
        if jwt_cfg:
            if not os.getenv('GRAFANA_RENDERER_JWT_AUTH_MODE'):
                jwt_auth_mode = jwt_cfg.get('mode', jwt_auth_mode)
            if not os.getenv('GRAFANA_RENDERER_JWT_AUTH_ENABLED'):
                jwt_auth_enabled = jwt_cfg.get('enabled', jwt_auth_enabled)
            if not os.getenv('GRAFANA_RENDERER_JWT_AUTH_KEYS_DIR'):
                jwt_auth_keys_dir = jwt_cfg.get('keys_dir', jwt_auth_keys_dir)
            if not os.getenv('GRAFANA_RENDERER_JWT_AUTH_KID'):
                jwt_auth_kid = jwt_cfg.get('kid', jwt_auth_kid)
            if not os.getenv('GRAFANA_RENDERER_JWT_AUTH_ISSUER'):
                jwt_auth_issuer = jwt_cfg.get('issuer', jwt_auth_issuer)
            if not os.getenv('GRAFANA_RENDERER_JWT_AUTH_AUDIENCE'):
                jwt_auth_audience = jwt_cfg.get('audience', jwt_auth_audience)
            if not os.getenv('GRAFANA_RENDERER_JWT_AUTH_TTL_SECONDS'):
                jwt_auth_ttl_seconds = jwt_cfg.get('ttl_seconds', jwt_auth_ttl_seconds)
            if not os.getenv('GRAFANA_RENDERER_JWT_AUTH_ROTATION_ENABLED'):
                jwt_auth_rotation_enabled = jwt_cfg.get('rotation_enabled', jwt_auth_rotation_enabled)
            if not os.getenv('GRAFANA_RENDERER_JWT_AUTH_ROTATION_INTERVAL_DAYS'):
                jwt_auth_rotation_interval_days = jwt_cfg.get('rotation_interval_days', jwt_auth_rotation_interval_days)
            if not os.getenv('GRAFANA_RENDERER_JWT_AUTH_GRACE_PERIOD_SECONDS'):
                jwt_auth_grace_period_seconds = jwt_cfg.get('grace_period_seconds', jwt_auth_grace_period_seconds)
            if not os.getenv('GRAFANA_RENDERER_JWT_AUTH_MAX_KEYS'):
                jwt_auth_max_keys = jwt_cfg.get('max_keys', jwt_auth_max_keys)

        # External JWT provider nested configuration: grafana_renderer.external_jwt
        ext_cfg = settings.get('grafana_renderer', {}).get('jwt_auth', {}).get('external_jwt', {})
        if ext_cfg:
            if not os.getenv('GRAFANA_RENDERER_EXTERNAL_JWT_ENV_VAR_NAME'):
                external_jwt_env_var_name = ext_cfg.get('env_var_name', external_jwt_env_var_name)
            if not os.getenv('GRAFANA_RENDERER_EXTERNAL_JWT_HTTP_URL'):
                external_jwt_http_url = ext_cfg.get('http_url', external_jwt_http_url)
            if not os.getenv('GRAFANA_RENDERER_EXTERNAL_JWT_HTTP_METHOD'):
                external_jwt_http_method = ext_cfg.get('http_method', external_jwt_http_method)
            if not os.getenv('GRAFANA_RENDERER_EXTERNAL_JWT_HTTP_HEADERS'):
                external_jwt_http_headers = ext_cfg.get('http_headers', external_jwt_http_headers)
            if not os.getenv('GRAFANA_RENDERER_EXTERNAL_JWT_HTTP_BODY'):
                external_jwt_http_body = ext_cfg.get('http_body', external_jwt_http_body)
            if not os.getenv('GRAFANA_RENDERER_EXTERNAL_JWT_HTTP_TOKEN_JSON_PATH'):
                external_jwt_http_token_json_path = ext_cfg.get('http_token_json_path', external_jwt_http_token_json_path)
            if not os.getenv('GRAFANA_RENDERER_EXTERNAL_JWT_HTTP_CACHE_TTL_SECONDS'):
                external_jwt_http_cache_ttl_seconds = ext_cfg.get('http_cache_ttl_seconds', external_jwt_http_cache_ttl_seconds)
            if not os.getenv('GRAFANA_RENDERER_EXTERNAL_JWT_HTTP_TIMEOUT_SECONDS'):
                external_jwt_http_timeout_seconds = ext_cfg.get('http_timeout_seconds', external_jwt_http_timeout_seconds)
            if not os.getenv('GRAFANA_RENDERER_EXTERNAL_JWT_HTTP_RETRIES'):
                external_jwt_http_retries = ext_cfg.get('http_retries', external_jwt_http_retries)
            if not os.getenv('GRAFANA_RENDERER_EXTERNAL_JWT_HTTP_RETRY_BACKOFF_MS'):
                external_jwt_http_retry_backoff_ms = ext_cfg.get('http_retry_backoff_ms', external_jwt_http_retry_backoff_ms)
            if not os.getenv('GRAFANA_RENDERER_EXTERNAL_JWT_CLOCK_SKEW_SECONDS'):
                external_jwt_clock_skew_seconds = ext_cfg.get('clock_skew_seconds', external_jwt_clock_skew_seconds)
            if not os.getenv('GRAFANA_RENDERER_EXTERNAL_JWT_ALLOW_FALLBACK_TO_DISABLED'):
                external_jwt_allow_fallback_to_disabled = ext_cfg.get('allow_fallback_to_disabled', external_jwt_allow_fallback_to_disabled)

        # Panel variables configuration: grafana_renderer.panel_variables
        panel_vars_cfg = settings.get('grafana_renderer', {}).get('panel_variables', {})
        if panel_vars_cfg:
            if not os.getenv('GRAFANA_RENDERER_PANEL_VARIABLES_MAX_VALUES_PER_VAR'):
                panel_variables_max_values_per_var = panel_vars_cfg.get('max_values_per_var', panel_variables_max_values_per_var)
            if not os.getenv('GRAFANA_RENDERER_PANEL_VARIABLES_MAX_URL_LENGTH'):
                panel_variables_max_url_length = panel_vars_cfg.get('max_url_length', panel_variables_max_url_length)
                
    except yaml.YAMLError as e:
        print(f"Error reading YAML file: {e}")
