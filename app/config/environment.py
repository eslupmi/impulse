import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_optional_int(name: str) -> int | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return None
    return int(value)


def _env_optional_float(name: str) -> float | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return None
    return float(value)


class EnvironmentConfig(BaseModel):
    """Environment-based configuration loaded from environment variables"""
    
    # Authentication tokens and secrets
    slack_bot_user_oauth_token: str = Field(
        default_factory=lambda: os.getenv('SLACK_BOT_USER_OAUTH_TOKEN', ''),
        description="Slack Bot User OAuth Token"
    )
    slack_verification_token: str = Field(
        default_factory=lambda: os.getenv('SLACK_VERIFICATION_TOKEN', ''),
        description="Slack Verification Token"
    )
    mattermost_access_token: str = Field(
        default_factory=lambda: os.getenv('MATTERMOST_ACCESS_TOKEN', ''),
        description="Mattermost Access Token"
    )
    telegram_bot_token: str = Field(
        default_factory=lambda: os.getenv('TELEGRAM_BOT_TOKEN', ''),
        description="Telegram Bot Token"
    )
    auth_client_id: str = Field(
        default_factory=lambda: os.getenv('AUTH_CLIENT_ID', ''),
        description="OAuth client id for messenger auth"
    )
    auth_client_secret: str = Field(
        default_factory=lambda: os.getenv('AUTH_CLIENT_SECRET', ''),
        description="OAuth client secret for messenger auth"
    )
    auth_redirect_url: str = Field(
        default_factory=lambda: os.getenv('AUTH_REDIRECT_URL', ''),
        description="Full redirect URL for OAuth callback (e.g., 'https://domain.com/auth/callback')"
    )
    auth_cookie_secure: bool = Field(
        default_factory=lambda: _env_bool('AUTH_COOKIE_SECURE', True),
        description="Set auth cookie with Secure attribute"
    )
    auth_whitelist_enabled: bool = Field(
        default_factory=lambda: _env_bool('AUTH_WHITELIST_ENABLED', True),
        description="Allow only users configured in impulse.yml messenger.users"
    )
    
    # Jira integration (Cloud with Basic Auth)
    jira_base_url: str = Field(
        default_factory=lambda: os.getenv('JIRA_BASE_URL', ''),
        description="Jira base URL (e.g., 'https://your-domain.atlassian.net')"
    )
    jira_user_email: str = Field(
        default_factory=lambda: os.getenv('JIRA_USER_EMAIL', ''),
        description="Jira user email for Basic Auth"
    )
    jira_api_token: str = Field(
        default_factory=lambda: os.getenv('JIRA_API_TOKEN', ''),
        description="Jira API token for Basic Auth"
    )
    
    # Paths
    data_path: str = Field(
        default_factory=lambda: os.getenv('DATA_PATH', './data'),
        description="Path to data directory"
    )
    config_path: str = Field(
        default_factory=lambda: os.getenv('CONFIG_PATH', './'),
        description="Path to configuration directory"
    )
    
    # Provider settings (for Google Calendar integration)
    provider_sync_interval: int = Field(
        default_factory=lambda: int(os.getenv('CHAIN_PROVIDER_SYNC_INTERVAL_SECONDS', '60')),
        description="Provider sync interval in seconds"
    )
    provider_max_events: int = Field(
        default_factory=lambda: int(os.getenv('CHAIN_PROVIDER_MAX_EVENTS', '10')),
        description="Maximum events to sync from provider"
    )
    provider_days_to_sync: int = Field(
        default_factory=lambda: int(os.getenv('CHAIN_PROVIDER_DAYS_TO_SYNC', '7')),
        description="Number of days to sync from provider"
)
    provider_service_account_file: str = Field(
        default_factory=lambda: os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', './key.json'),
        description="Path to Google service account file"
    )
    
    # CORS configuration
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: os.getenv('CORS_ALLOWED_ORIGINS', 'https://localhost:5000').split(','),
        description="Comma-separated list of allowed CORS origins"
    )
    
    # Logging
    log_level: str = Field(
        default_factory=lambda: os.getenv('LOG_LEVEL', 'INFO'),
        description="Logging level"
    )
    
    # HTTP prefix configuration
    http_prefix: str = Field(
        default_factory=lambda: os.getenv('HTTP_PREFIX', ''),
        description="HTTP prefix for reverse proxy deployments (e.g., '/impulse')"
    )
    
    # Server configuration
    listen_host: str = Field(
        default_factory=lambda: os.getenv('LISTEN_HOST', '0.0.0.0'),
        description="Host to listen on"
    )
    listen_port: int = Field(
        default_factory=lambda: int(os.getenv('LISTEN_PORT', '5000')),
        description="Port to listen on"
    )
    messenger_rate_limit: int | None = Field(
        default_factory=lambda: _env_optional_int('MESSENGER_RATE_LIMIT'),
        description="Override messenger HTTP request limit (0 disables limiting)"
    )
    messenger_rate_window: float | None = Field(
        default_factory=lambda: _env_optional_float('MESSENGER_RATE_WINDOW'),
        description="Override messenger HTTP rate-limit window in seconds"
    )

    @field_validator('provider_sync_interval', 'provider_max_events', 'provider_days_to_sync', 'listen_port')
    @classmethod
    def validate_positive_integers(cls, v):
        """Validate that numeric settings are positive integers"""
        if v <= 0:
            raise ValueError("Configuration values must be positive integers")
        return v
    
    @field_validator('cors_allowed_origins')
    @classmethod
    def validate_cors_origins(cls, v):
        """Clean up CORS origins by removing whitespace"""
        return [origin.strip() for origin in v if origin.strip()]
    
    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level is valid"""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {', '.join(valid_levels)}")
        return v.upper()
    
    @field_validator('messenger_rate_limit')
    @classmethod
    def validate_messenger_rate_limit(cls, v):
        if v is not None and v < 0:
            raise ValueError("MESSENGER_RATE_LIMIT must be >= 0")
        return v

    @field_validator('messenger_rate_window')
    @classmethod
    def validate_messenger_rate_window(cls, v):
        if v is not None and v <= 0:
            raise ValueError("MESSENGER_RATE_WINDOW must be positive")
        return v

    @field_validator('http_prefix')
    @classmethod
    def validate_http_prefix(cls, v):
        """Validate HTTP prefix format"""
        if v and not v.startswith('/'):
            raise ValueError("HTTP prefix must start with '/' (e.g., '/impulse')")
        if v and v.endswith('/'):
            raise ValueError("HTTP prefix must not end with '/' (e.g., '/impulse' not '/impulse/')")
        return v

    @field_validator('jira_base_url')
    @classmethod
    def normalize_jira_base_url(cls, v):
        return v.rstrip("/") if v else v
    
    def apply_messenger_rate_limits(
        self, rate_limit: int | None, rate_window: float
    ) -> tuple[int | None, float]:
        if self.messenger_rate_limit is not None:
            rate_limit = self.messenger_rate_limit if self.messenger_rate_limit > 0 else None
        if self.messenger_rate_window is not None:
            rate_window = self.messenger_rate_window
        return rate_limit, rate_window

    @property
    def incidents_path(self) -> str:
        """Computed property for incidents path"""
        return f"{self.data_path}/incidents"
    
    @property
    def config_file_path(self) -> str:
        """Computed property for config file path"""
        return os.path.join(self.config_path, "impulse.yml")
    
    @property
    def task_management_enabled(self) -> bool:
        """Check if Task management integration is enabled (all required fields are set)"""
        return all([
            self.jira_base_url,
            self.jira_user_email,
            self.jira_api_token
        ])


# Global instance - created once and reused
_env_config: EnvironmentConfig | None = None


def get_environment_config() -> EnvironmentConfig:
    """Get the singleton instance of environment configuration"""
    global _env_config
    if _env_config is None:
        _env_config = EnvironmentConfig()
    return _env_config
