import os
from typing import Dict, Any, Tuple

import yaml
from pydantic import ValidationError

from app.config.validation import ImpulseConfig, validate_config


class ConfigValidationError(Exception):
    """Custom exception for configuration validation errors"""
    
    def __init__(self, message: str, validation_errors: list = None):
        super().__init__(message)
        self.validation_errors = validation_errors or []


def load_and_validate_config(config_path: str = None) -> Tuple[ImpulseConfig, Dict[str, Any]]:
    # Determine config path
    if config_path is None:
        config_path = os.getenv('CONFIG_PATH', './') + '/impulse.yml'
    
    # Check if file exists
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    # Load YAML file
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            raw_config = yaml.safe_load(file)
    except yaml.YAMLError as e:
        raise ConfigValidationError(f"YAML parsing failed: {e}")
    except Exception as e:
        raise ConfigValidationError(f"Failed to read config file: {e}")
    
    if raw_config is None:
        raise ConfigValidationError("Configuration file is empty")
    
    # Validate configuration
    try:
        validated_config = validate_config(raw_config)
        return validated_config, raw_config
    except ValidationError as e:
        error_details = []
        for error in e.errors():
            loc = " -> ".join(str(x) for x in error['loc'])
            error_details.append(f"  {loc}: {error['msg']}")
        
        error_message = "Configuration validation failed:\n" + "\n".join(error_details)
        raise ConfigValidationError(error_message, e.errors())
