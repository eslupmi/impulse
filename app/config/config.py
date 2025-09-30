from typing import Optional

from app.config.environment import get_environment_config, EnvironmentConfig
from app.config.loader import load_and_validate_config, ConfigValidationError
from app.config.validation import ImpulseConfig
from app.logging import logger


class UnifiedConfig:
    """
    Unified configuration that combines environment and validated application config.
    Uses existing ImpulseConfig as source of truth for application configuration.
    """

    def __init__(self, env: EnvironmentConfig, app: ImpulseConfig):
        self.env = env
        self.app = app

        self.INCIDENT_ACTUAL_VERSION = 'v3.0.0'
        self.check_updates = True

    @property
    def incident(self):
        return self.app.incident

    @property
    def messenger(self):
        return self.app.messenger

    @property
    def ui_config(self):
        return self.app.ui

    @property
    def slack_bot_user_oauth_token(self) -> str:
        return self.env.slack_bot_user_oauth_token

    @property
    def slack_verification_token(self) -> str:
        return self.env.slack_verification_token

    @property
    def mattermost_access_token(self) -> str:
        return self.env.mattermost_access_token

    @property
    def telegram_bot_token(self) -> str:
        return self.env.telegram_bot_token

    @property
    def data_path(self) -> str:
        return self.env.data_path

    @property
    def config_path(self) -> str:
        return self.env.config_path

    @property
    def incidents_path(self) -> str:
        return self.env.incidents_path

    @property
    def provider_sync_interval(self) -> int:
        return self.env.provider_sync_interval

    @property
    def provider_max_events(self) -> int:
        return self.env.provider_max_events

    @property
    def provider_days_to_sync(self) -> int:
        return self.env.provider_days_to_sync

    @property
    def provider_service_account_file(self) -> str:
        return self.env.provider_service_account_file

    @property
    def cors_allowed_origins(self) -> list:
        return self.env.cors_allowed_origins


_config: Optional[UnifiedConfig] = None


def get_config() -> UnifiedConfig:
    """
    Get the global configuration instance.
    """
    global _config
    if _config is None:
        _config = load_unified_config()
    return _config


def load_unified_config(config_path: Optional[str] = None, exit_on_error: bool = True) -> UnifiedConfig:
    """
    Load and create unified configuration from environment and YAML file.
    
    Args:
        config_path: Optional path to configuration file. Uses env CONFIG_PATH if not provided.
        exit_on_error: If True, exit process on validation errors. If False, raise exception.
        
    Returns:
        UnifiedConfig: Complete configuration object
        
    Raises:
        ConfigValidationError: If configuration loading or validation fails
        SystemExit: If configuration is invalid and exit_on_error is True
    """
    try:
        env_config = get_environment_config()

        if config_path is None:
            config_path = env_config.config_file_path

        validated_config, raw_config = load_and_validate_config(config_path)

        return UnifiedConfig(
            env=env_config,
            app=validated_config
        )

    except ConfigValidationError as e:
        error_msg = (f"{e}\n"
                     f"Please check your impulse.yml file and fix any validation errors.\n"
                     f"Documentation: https://docs.impulse.bot/stable/config_file/")
        if exit_on_error:
            logger.error(error_msg)
            raise SystemExit(1)
        else:
            logger.warning(error_msg)
            raise
    except Exception as e:
        error_msg = f"Failed to load configuration: {e}"
        if exit_on_error:
            logger.error(error_msg)
            raise SystemExit(1)
        else:
            logger.warning(error_msg)
            raise


def reload_config(config_path: Optional[str] = None) -> bool:
    """
    Reload configuration from file with graceful error handling.
    If validation fails, keeps the current configuration and logs a warning.
    
    Args:
        config_path: Optional path to configuration file. Uses env CONFIG_PATH if not provided.
        
    Returns:
        bool: True if reload was successful, False if failed and kept old config
    """
    global _config
    current_config = _config

    try:
        new_config = load_unified_config(config_path, exit_on_error=False)
        if new_config.app.application.type == current_config.app.application.type:
            _config = new_config
            logger.info("Configuration reloaded successfully")
            return True
        else:
            logger.warning("Application type changed, keeping current configuration")
            return False

    except ConfigValidationError as e:
        logger.warning("Configuration validation failed, keeping current configuration")
        _config = current_config
        return False
    except Exception as e:
        logger.warning(f"Configuration reload failed, keeping current configuration: {e}")
        _config = current_config
        return False


def force_reload_config(config_path: Optional[str] = None) -> UnifiedConfig:
    """
    Force reload configuration from file (original behavior).
    Useful for testing or when you want the process to exit on validation errors.
    """
    global _config
    _config = load_unified_config(config_path)
    return _config
