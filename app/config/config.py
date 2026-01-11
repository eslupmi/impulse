from typing import Optional

from app.config.environment import get_environment_config
from app.config.loader import load_and_validate_config, ConfigValidationError
from app.config.validation import ImpulseConfig
from app.logging import logger


class UnifiedConfig:
    """
    Unified configuration for application settings.
    Uses ImpulseConfig as source of truth for application configuration.
    Environment configuration should be accessed via get_environment_config().
    """

    def __init__(self, app: ImpulseConfig):
        self.app = app

        self.INCIDENT_ACTUAL_VERSION = 'v3.2.0'
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
    Load and create unified configuration from YAML file.
    
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

        validated_config, _ = load_and_validate_config(config_path)

        return UnifiedConfig(app=validated_config)

    except ConfigValidationError as e:
        if exit_on_error:
            logger.error("Config validation failed", extra={'error': str(e)})
            raise SystemExit(1)
        else:
            logger.warning("Config validation failed", extra={'error': str(e)})
            raise
    except Exception as e:
        if exit_on_error:
            logger.error("Config load failed", extra={'error': str(e)})
            raise SystemExit(1)
        else:
            logger.warning("Config load failed", extra={'error': str(e)})
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
        if new_config.messenger.type == current_config.messenger.type:
            _config = new_config
            return True
        else:
            logger.warning("Application type changed, keeping current configuration")
            return False

    except ConfigValidationError as e:
        logger.warning("Config validation failed, keeping current config", extra={'error': str(e)})
        _config = current_config
        return False
    except Exception as e:
        logger.warning("Config reload failed, keeping current config", extra={'error': str(e)})
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
