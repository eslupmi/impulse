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

        self.INCIDENT_ACTUAL_VERSION = 'v3.4.0'
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


def load_unified_config(exit_on_error: bool = True) -> UnifiedConfig:
    try:
        env_config = get_environment_config()
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


def validate_config_only():
    try:
        get_config()
        logger.info("Configuration valid")
    except Exception as e:
        logger.error("Configuration validation failed", extra={'error': str(e)})
        raise SystemExit(1)


def reload_config() -> bool:
    global _config
    current_config = _config

    try:
        new_config = load_unified_config(exit_on_error=False)
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
