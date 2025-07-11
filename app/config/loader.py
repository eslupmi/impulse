import os
import yaml
from typing import Dict, Any, Tuple
from pydantic import ValidationError

from app.config.validation import ImpulseConfig, validate_config


class ConfigValidationError(Exception):
    """Custom exception for configuration validation errors"""
    
    def __init__(self, message: str, validation_errors: list = None):
        super().__init__(message)
        self.validation_errors = validation_errors or []


def load_and_validate_config(config_path: str = None) -> Tuple[ImpulseConfig, Dict[str, Any]]:
    """
    Load and validate Impulse configuration from YAML file.
    
    Args:
        config_path: Path to the configuration file. If None, uses CONFIG_PATH env var
        
    Returns:
        tuple: (validated_config, raw_config_dict)
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML parsing fails
        ConfigValidationError: If validation fails
    """
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
        
        error_message = f"Configuration validation failed:\n" + "\n".join(error_details)
        raise ConfigValidationError(error_message, e.errors())


def get_legacy_config_dict(validated_config: ImpulseConfig) -> Dict[str, Any]:
    """
    Convert validated Pydantic config to legacy dictionary format for backward compatibility.
    
    Args:
        validated_config: Validated Pydantic configuration object
        
    Returns:
        dict: Configuration in legacy format
    """
    # Convert to dict and restructure for legacy code
    config_dict = validated_config.model_dump()
    
    # Legacy format adjustments
    legacy_config = {
        'application': config_dict['application'],
        'incident': config_dict.get('incident', {}),
        'experimental': config_dict.get('experimental', {}),
        'route': config_dict['route'],
        'ui': config_dict.get('ui', {}),
        'webhooks': config_dict.get('webhooks', {})
    }
    
    # Ensure template_files is properly handled in application section
    if 'template_files' not in legacy_config['application'] or legacy_config['application']['template_files'] is None:
        legacy_config['application']['template_files'] = {}
    
    # Ensure incident defaults
    if 'incident' not in legacy_config or legacy_config['incident'] is None:
        legacy_config['incident'] = {}
    
    incident_defaults = {
        'alerts_firing_notifications': False,
        'alerts_resolved_notifications': False,
        'timeouts': {
            'firing': '6h',
            'unknown': '6h', 
            'resolved': '12h'
        }
    }
    
    for key, default_value in incident_defaults.items():
        if key not in legacy_config['incident']:
            legacy_config['incident'][key] = default_value
    
    # Ensure experimental defaults
    if 'experimental' not in legacy_config or legacy_config['experimental'] is None:
        legacy_config['experimental'] = {}
    
    experimental_defaults = {
        'recreate_chain': False
    }
    
    for key, default_value in experimental_defaults.items():
        if key not in legacy_config['experimental']:
            legacy_config['experimental'][key] = default_value
    
    return legacy_config


def format_validation_errors(errors: list) -> str:
    """
    Format validation errors for user-friendly display.
    
    Args:
        errors: List of validation error messages
        
    Returns:
        Formatted error string
    """
    if not errors:
        return "No validation errors"
    
    formatted_errors = []
    for i, error in enumerate(errors, 1):
        formatted_errors.append(f"{i}. {error}")
    
    return f"Configuration validation errors:\n" + "\n".join(formatted_errors)


def validate_config_and_show_errors(config_path: str = None) -> ImpulseConfig:
    """
    Validate configuration and show user-friendly errors on failure.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        Validated configuration object
        
    Raises:
        SystemExit: If validation fails (after showing errors)
    """
    try:
        validated_config, _ = load_and_validate_config(config_path)
        return validated_config
    except FileNotFoundError as e:
        print(f"\nConfiguration file not found: {e}")
        raise SystemExit(1)
    except yaml.YAMLError as e:
        print(f"\nYAML parsing error: {e}")
        raise SystemExit(1) 