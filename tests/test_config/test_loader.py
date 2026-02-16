"""
Unit tests for app.config.loader module.
"""
from unittest.mock import Mock, patch, mock_open

import pytest
import yaml

from app.config.loader import (
    load_and_validate_config,
    ConfigValidationError
)
from app.config.validation import ImpulseConfig, MessengerType
from tests.utils import (
    create_slack_config_data, create_mock_impulse_config
)


class TestLoadAndValidateConfig:
    """Test cases for load_and_validate_config function."""

    def test_load_valid_config(self):
        """Test loading a valid configuration file."""
        valid_config = create_slack_config_data()

        with patch('builtins.open', mock_open(read_data=yaml.dump(valid_config))):
            with patch('os.path.exists', return_value=True):
                config, raw_config = load_and_validate_config('test_config.yml')

        assert isinstance(config, ImpulseConfig)
        assert config.messenger.type == MessengerType.SLACK
        assert raw_config == valid_config

    def test_load_config_file_not_found(self):
        """Test loading a non-existent configuration file."""
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            load_and_validate_config('nonexistent.yml')

    def test_load_config_invalid_yaml(self):
        """Test loading a file with invalid YAML."""
        invalid_yaml = "messenger:\n  type: [invalid yaml"

        with patch('builtins.open', mock_open(read_data=invalid_yaml)):
            with patch('os.path.exists', return_value=True):
                with pytest.raises(ConfigValidationError, match="YAML parsing failed"):
                    load_and_validate_config('invalid.yml')

    def test_load_config_empty_file(self):
        """Test loading an empty configuration file."""
        with patch('builtins.open', mock_open(read_data='')):
            with patch('os.path.exists', return_value=True):
                with pytest.raises(ConfigValidationError, match="Configuration file is empty"):
                    load_and_validate_config('empty.yml')

    def test_load_config_none_content(self):
        """Test loading a file that results in None content."""
        with patch('builtins.open', mock_open(read_data='---\n')):
            with patch('os.path.exists', return_value=True):
                with pytest.raises(ConfigValidationError, match="Configuration file is empty"):
                    load_and_validate_config('none.yml')

    def test_load_config_validation_error(self):
        """Test loading a config with validation errors."""
        invalid_config = {
            'messenger': {
                'type': 'invalid_type',  # Invalid messenger type
                'channels': {},
                'users': {}
            }
        }

        with patch('builtins.open', mock_open(read_data=yaml.dump(invalid_config))):
            with patch('os.path.exists', return_value=True):
                with pytest.raises(ConfigValidationError, match="Configuration validation failed"):
                    load_and_validate_config('invalid_config.yml')

    def test_load_config_missing_required_fields(self):
        """Test loading a config with missing required fields."""
        incomplete_config = {
            'messenger': {
                'type': 'slack'
                # Missing channels, users, etc.
            }
        }

        with patch('builtins.open', mock_open(read_data=yaml.dump(incomplete_config))):
            with patch('os.path.exists', return_value=True):
                with pytest.raises(ConfigValidationError, match="Configuration validation failed"):
                    load_and_validate_config('incomplete.yml')

    def test_load_config_file_read_error(self):
        """Test handling of file read errors."""
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            with patch('os.path.exists', return_value=True):
                with pytest.raises(ConfigValidationError, match="Failed to read config file"):
                    load_and_validate_config('protected.yml')

    def test_load_config_with_env_var_path(self):
        """Test loading config using CONFIG_PATH environment variable."""
        valid_config = create_slack_config_data()

        with patch('builtins.open', mock_open(read_data=yaml.dump(valid_config))):
            with patch('os.path.exists', return_value=True):
                with patch.dict('os.environ', {'CONFIG_PATH': '/custom/path'}):
                    config, _ = load_and_validate_config()

        assert isinstance(config, ImpulseConfig)

    def test_load_config_custom_path(self):
        """Test loading config with custom path."""
        valid_config = create_slack_config_data()

        with patch('builtins.open', mock_open(read_data=yaml.dump(valid_config))) as mock_file:
            with patch('os.path.exists', return_value=True):
                config, _ = load_and_validate_config('/custom/path/config.yml')

        mock_file.assert_called_once_with('/custom/path/config.yml', 'r', encoding='utf-8')
        assert isinstance(config, ImpulseConfig)


class TestConfigValidationError:
    """Test cases for ConfigValidationError exception."""

    def test_config_validation_error_creation(self):
        """Test creating ConfigValidationError with message only."""
        error = ConfigValidationError("Test error message")
        assert str(error) == "Test error message"
        assert error.validation_errors == []

    def test_config_validation_error_with_validation_errors(self):
        """Test creating ConfigValidationError with validation errors."""
        validation_errors = [
            {'loc': ('messenger', 'type'), 'msg': 'Invalid type'},
            {'loc': ('route', 'channel'), 'msg': 'Required field'}
        ]
        error = ConfigValidationError("Validation failed", validation_errors)
        assert str(error) == "Validation failed"
        assert error.validation_errors == validation_errors

    def test_config_validation_error_inheritance(self):
        """Test that ConfigValidationError inherits from Exception."""
        error = ConfigValidationError("Test error")
        assert isinstance(error, Exception)
