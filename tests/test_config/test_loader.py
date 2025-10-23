"""
Unit tests for app.config.loader module.
"""
from unittest.mock import Mock, patch, mock_open

import pytest
import yaml

from app.config.loader import (
    load_and_validate_config,
    get_legacy_config_dict,
    ConfigValidationError,
    format_validation_errors,
    validate_config_and_show_errors
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
                    config, raw_config = load_and_validate_config()

        assert isinstance(config, ImpulseConfig)

    def test_load_config_custom_path(self):
        """Test loading config with custom path."""
        valid_config = create_slack_config_data()

        with patch('builtins.open', mock_open(read_data=yaml.dump(valid_config))) as mock_file:
            with patch('os.path.exists', return_value=True):
                config, raw_config = load_and_validate_config('/custom/path/config.yml')

        mock_file.assert_called_once_with('/custom/path/config.yml', 'r', encoding='utf-8')
        assert isinstance(config, ImpulseConfig)


class TestGetLegacyConfigDict:
    """Test cases for get_legacy_config_dict function."""

    def test_convert_to_legacy_format(self):
        """Test converting validated config to legacy format."""
        # Create a mock validated config using utility
        mock_config = create_mock_impulse_config()
        mock_config.model_dump.return_value = {
            'messenger': {
                'type': 'slack',
                'channels': {'default': {'id': 'C123456789'}},
                'users': {},
                'template_files': {}
            },
            'incident': {
                'alerts_firing_notifications': True,
                'timeouts': {'firing': '6h'}
            },
            'route': {'channel': 'default'},
            'ui': True,
            'webhooks': {'test': {'url': 'http://test.com'}}
        }

        legacy_config = get_legacy_config_dict(mock_config)

        assert legacy_config['messenger']['type'] == 'slack'
        assert legacy_config['incident']['alerts_firing_notifications'] is True
        assert legacy_config['route']['channel'] == 'default'
        assert legacy_config['ui'] is True
        assert legacy_config['webhooks']['test']['url'] == 'http://test.com'

    def test_convert_with_none_incident(self):
        """Test converting config with None incident section."""
        mock_config = Mock(spec=ImpulseConfig)
        mock_config.model_dump.return_value = {
            'messenger': {'type': 'slack', 'channels': {}, 'users': {}, 'template_files': {}},
            'incident': None,
            'route': {'channel': 'default'},
            'ui': True,
            'webhooks': {}
        }

        legacy_config = get_legacy_config_dict(mock_config)

        # Should have default incident settings
        assert legacy_config['incident']['alerts_firing_notifications'] is False
        assert legacy_config['incident']['alerts_resolved_notifications'] is False
        assert legacy_config['incident']['timeouts']['firing'] == '6h'

    def test_convert_with_missing_template_files(self):
        """Test converting config with missing template_files."""
        mock_config = Mock(spec=ImpulseConfig)
        mock_config.model_dump.return_value = {
            'messenger': {
                'type': 'slack',
                'channels': {},
                'users': {},
                'template_files': None
            },
            'route': {'channel': 'default'},
            'ui': True,
            'webhooks': {}
        }

        legacy_config = get_legacy_config_dict(mock_config)

        # Should have empty template_files
        assert legacy_config['messenger']['template_files'] == {}

    def test_convert_with_missing_ui(self):
        """Test converting config with missing UI section."""
        mock_config = Mock(spec=ImpulseConfig)
        mock_config.model_dump.return_value = {
            'messenger': {'type': 'slack', 'channels': {}, 'users': {}, 'template_files': {}},
            'route': {'channel': 'default'},
            'ui': None,
            'webhooks': {}
        }

        legacy_config = get_legacy_config_dict(mock_config)

        # Should have default UI settings when ui is None
        # The actual implementation returns None for ui when it's None
        assert legacy_config['ui'] is None

    def test_convert_with_missing_webhooks(self):
        """Test converting config with missing webhooks."""
        mock_config = Mock(spec=ImpulseConfig)
        mock_config.model_dump.return_value = {
            'messenger': {'type': 'slack', 'channels': {}, 'users': {}, 'template_files': {}},
            'route': {'channel': 'default'},
            'ui': True
            # No webhooks key
        }

        legacy_config = get_legacy_config_dict(mock_config)

        # Should have empty webhooks
        assert legacy_config['webhooks'] == {}

    def test_convert_with_complex_incident_config(self):
        """Test converting config with complex incident configuration."""
        mock_config = Mock(spec=ImpulseConfig)
        mock_config.model_dump.return_value = {
            'messenger': {'type': 'slack', 'channels': {}, 'users': {}, 'template_files': {}},
            'incident': {
                'alerts_firing_notifications': True,
                'alerts_resolved_notifications': True,
                'timeouts': {
                    'firing': '2h',
                    'unknown': '1h',
                    'resolved': '30m'
                }
            },
            'route': {'channel': 'default'},
            'ui': True,
            'webhooks': {}
        }

        legacy_config = get_legacy_config_dict(mock_config)

        # Should preserve existing incident settings
        assert legacy_config['incident']['alerts_firing_notifications'] is True
        assert legacy_config['incident']['alerts_resolved_notifications'] is True
        assert legacy_config['incident']['timeouts']['firing'] == '2h'
        assert legacy_config['incident']['timeouts']['unknown'] == '1h'
        assert legacy_config['incident']['timeouts']['resolved'] == '30m'

    def test_convert_with_partial_incident_config(self):
        """Test converting config with partial incident configuration."""
        mock_config = Mock(spec=ImpulseConfig)
        mock_config.model_dump.return_value = {
            'messenger': {'type': 'slack', 'channels': {}, 'users': {}, 'template_files': {}},
            'incident': {
                'alerts_firing_notifications': True
                # Missing other fields
            },
            'route': {'channel': 'default'},
            'ui': True,
            'webhooks': {}
        }

        legacy_config = get_legacy_config_dict(mock_config)

        # Should have existing settings and defaults for missing ones
        assert legacy_config['incident']['alerts_firing_notifications'] is True
        assert legacy_config['incident']['alerts_resolved_notifications'] is False  # Default
        assert legacy_config['incident']['timeouts']['firing'] == '6h'  # Default
        assert legacy_config['incident']['timeouts']['unknown'] == '6h'  # Default
        assert legacy_config['incident']['timeouts']['resolved'] == '12h'  # Default

    def test_convert_with_ui_config(self):
        """Test converting config with UI configuration."""
        mock_config = Mock(spec=ImpulseConfig)
        mock_config.model_dump.return_value = {
            'messenger': {'type': 'slack', 'channels': {}, 'users': {}, 'template_files': {}},
            'route': {'channel': 'default'},
            'ui': {
                'enabled': True,
                'table_config': {
                    'sorting': {'column': 'status', 'direction': 'asc'},
                    'filters': {'status': ['firing', 'resolved']}
                }
            },
            'webhooks': {}
        }

        legacy_config = get_legacy_config_dict(mock_config)

        # Should preserve UI configuration
        assert legacy_config['ui']['enabled'] is True
        assert legacy_config['ui']['table_config']['sorting']['column'] == 'status'
        assert legacy_config['ui']['table_config']['filters']['status'] == ['firing', 'resolved']


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


class TestFormatValidationErrors:
    """Test cases for format_validation_errors function."""

    def test_format_validation_errors_empty_list(self):
        """Test formatting empty validation errors list."""
        result = format_validation_errors([])
        assert result == "No validation errors"

    def test_format_validation_errors_single_error(self):
        """Test formatting single validation error."""
        errors = ["Field 'messenger.type' is required"]
        result = format_validation_errors(errors)

        expected = "Configuration validation errors:\n1. Field 'messenger.type' is required"
        assert result == expected

    def test_format_validation_errors_multiple_errors(self):
        """Test formatting multiple validation errors."""
        errors = [
            "Field 'messenger.type' is required",
            "Field 'route.channel' must be a string",
            "Field 'ui.enabled' must be a boolean"
        ]
        result = format_validation_errors(errors)

        expected = """Configuration validation errors:
1. Field 'messenger.type' is required
2. Field 'route.channel' must be a string
3. Field 'ui.enabled' must be a boolean"""
        assert result == expected

    def test_format_validation_errors_none_input(self):
        """Test formatting None input."""
        result = format_validation_errors(None)
        assert result == "No validation errors"


class TestValidateConfigAndShowErrors:
    """Test cases for validate_config_and_show_errors function."""

    def test_validate_config_and_show_errors_success(self):
        """Test successful configuration validation."""
        valid_config = create_slack_config_data()

        with patch('builtins.open', mock_open(read_data=yaml.dump(valid_config))):
            with patch('app.config.loader.load_and_validate_config') as mock_load:
                mock_config = Mock(spec=ImpulseConfig)
                mock_load.return_value = (mock_config, valid_config)

                result = validate_config_and_show_errors('test_config.yml')

                assert result is mock_config
                mock_load.assert_called_once_with('test_config.yml')

    def test_validate_config_and_show_errors_file_not_found(self):
        """Test handling of file not found error."""
        with patch('app.config.loader.load_and_validate_config', side_effect=FileNotFoundError("File not found")):
            with patch('app.config.loader.logger') as mock_logger:
                with pytest.raises(SystemExit) as exc_info:
                    validate_config_and_show_errors('nonexistent.yml')

                assert exc_info.value.code == 1
                mock_logger.error.assert_called_once_with("\nConfiguration file not found: File not found")

    def test_validate_config_and_show_errors_yaml_error(self):
        """Test handling of YAML parsing error."""
        with patch('app.config.loader.load_and_validate_config', side_effect=yaml.YAMLError("Invalid YAML")):
            with patch('app.config.loader.logger') as mock_logger:
                with pytest.raises(SystemExit) as exc_info:
                    validate_config_and_show_errors('invalid.yml')

                assert exc_info.value.code == 1
                mock_logger.error.assert_called_once_with("\nYAML parsing error: Invalid YAML")

    def test_validate_config_and_show_errors_validation_error(self):
        """Test handling of validation error."""
        validation_error = ConfigValidationError("Validation failed")

        with patch('app.config.loader.load_and_validate_config', side_effect=validation_error):
            with pytest.raises(ConfigValidationError, match="Validation failed"):
                validate_config_and_show_errors('invalid_config.yml')

    def test_validate_config_and_show_errors_no_path(self):
        """Test validation with no config path provided."""
        valid_config = create_slack_config_data()

        with patch('builtins.open', mock_open(read_data=yaml.dump(valid_config))):
            with patch('app.config.loader.load_and_validate_config') as mock_load:
                mock_config = Mock(spec=ImpulseConfig)
                mock_load.return_value = (mock_config, valid_config)

                result = validate_config_and_show_errors()

                assert result is mock_config
                mock_load.assert_called_once_with(None)
