"""
Unit tests for app.config.config module.
"""
from unittest.mock import Mock, patch

import pytest

from app.config.config import UnifiedConfig, get_config, load_unified_config, reload_config
from app.config.loader import ConfigValidationError
from app.config.validation import MessengerType


class TestUnifiedConfig:
    """Test cases for UnifiedConfig class."""

    def test_unified_config_creation(self, mock_impulse_config):
        """Test creation of UnifiedConfig."""
        config = UnifiedConfig(mock_impulse_config)

        assert config.app == mock_impulse_config
        assert config.INCIDENT_ACTUAL_VERSION == 'v3.6.0'
        assert config.check_updates is True

    def test_messenger_property(self, mock_impulse_config):
        """Test messenger property access."""
        config = UnifiedConfig(mock_impulse_config)
        assert config.messenger == mock_impulse_config.messenger

    def test_incident_property(self, mock_impulse_config):
        """Test incident property access."""
        config = UnifiedConfig(mock_impulse_config)
        assert config.incident == mock_impulse_config.incident

    def test_ui_config_property(self, mock_impulse_config):
        """Test ui_config property access."""
        config = UnifiedConfig(mock_impulse_config)
        assert config.ui_config == mock_impulse_config.ui


class TestConfigFunctions:
    """Test cases for configuration functions."""

    @patch('app.config.config._config', None)
    @patch('app.config.config.load_unified_config')
    def test_get_config_first_time(self, mock_load_unified_config, mock_unified_config):
        """Test get_config when called for the first time."""
        mock_load_unified_config.return_value = mock_unified_config

        result = get_config()

        mock_load_unified_config.assert_called_once()
        assert result == mock_unified_config

    @patch('app.config.config.load_unified_config')
    def test_get_config_cached(self, mock_load_unified_config, mock_unified_config):
        """Test get_config when config is already cached."""
        # Set the global _config variable to simulate cached config
        with patch('app.config.config._config', mock_unified_config):
            result = get_config()

            mock_load_unified_config.assert_not_called()
            assert result == mock_unified_config

    @patch('app.config.config.get_environment_config')
    @patch('app.config.config.load_and_validate_config')
    def test_load_unified_config_success(self, mock_load_and_validate, mock_get_env_config,
                                         mock_environment_config, mock_impulse_config):
        """Test successful loading of unified config."""
        mock_get_env_config.return_value = mock_environment_config
        mock_load_and_validate.return_value = (mock_impulse_config, {})
        mock_environment_config.config_file_path = "test_config.yml"

        result = load_unified_config()

        mock_get_env_config.assert_called_once()
        mock_load_and_validate.assert_called_once_with("test_config.yml")
        assert isinstance(result, UnifiedConfig)
        assert result.app == mock_impulse_config

    @patch('app.config.config.get_environment_config')
    @patch('app.config.config.load_and_validate_config')
    @patch('app.config.config.logger')
    def test_load_unified_config_validation_error_exit(self, mock_logger, mock_load_and_validate,
                                                       mock_get_env_config, mock_environment_config):
        """Test loading unified config with validation error and exit_on_error=True."""
        mock_get_env_config.return_value = mock_environment_config
        mock_load_and_validate.side_effect = ConfigValidationError("Test validation error")

        with pytest.raises(SystemExit):
            load_unified_config()

        mock_logger.error.assert_called_once()

    @patch('app.config.config.get_environment_config')
    @patch('app.config.config.load_and_validate_config')
    @patch('app.config.config.logger')
    def test_load_unified_config_validation_error_no_exit(self, mock_logger, mock_load_and_validate,
                                                          mock_get_env_config, mock_environment_config):
        """Test loading unified config with validation error and exit_on_error=False."""
        mock_get_env_config.return_value = mock_environment_config
        mock_load_and_validate.side_effect = ConfigValidationError("Test validation error")

        with pytest.raises(ConfigValidationError):
            load_unified_config(exit_on_error=False)

        mock_logger.warning.assert_called_once()

    @patch('app.config.config.get_environment_config')
    @patch('app.config.config.load_and_validate_config')
    @patch('app.config.config.logger')
    def test_load_unified_config_general_error_exit(self, mock_logger, mock_load_and_validate,
                                                    mock_get_env_config, mock_environment_config):
        """Test loading unified config with general error and exit_on_error=True."""
        mock_get_env_config.return_value = mock_environment_config
        mock_load_and_validate.side_effect = Exception("General error")

        with pytest.raises(SystemExit):
            load_unified_config()

        mock_logger.error.assert_called_once()

    @patch('app.config.config.get_environment_config')
    @patch('app.config.config.load_and_validate_config')
    @patch('app.config.config.logger')
    def test_load_unified_config_general_error_no_exit(self, mock_logger, mock_load_and_validate,
                                                       mock_get_env_config, mock_environment_config):
        """Test loading unified config with general error and exit_on_error=False."""
        mock_get_env_config.return_value = mock_environment_config
        mock_load_and_validate.side_effect = Exception("General error")

        with pytest.raises(Exception):
            load_unified_config(exit_on_error=False)

        mock_logger.warning.assert_called_once()

    @patch('app.config.config._config')
    @patch('app.config.config.load_unified_config')
    @patch('app.config.config.logger')
    def test_reload_config_success(self, mock_logger, mock_load_unified_config,
                                   mock_current_config, mock_unified_config):
        """Test successful config reload."""
        # Setup current config
        mock_current_config.messenger.type = MessengerType.SLACK

        # Setup new config
        mock_new_config = Mock()
        mock_new_config.messenger.type = MessengerType.SLACK
        mock_load_unified_config.return_value = mock_new_config

        result = reload_config()

        assert result is True
        mock_load_unified_config.assert_called_once_with(exit_on_error=False)

    @patch('app.config.config._config')
    @patch('app.config.config.load_unified_config')
    @patch('app.config.config.logger')
    def test_reload_config_type_change(self, mock_logger, mock_load_unified_config,
                                       mock_current_config, mock_unified_config):
        """Test config reload with messenger type change."""
        # Setup current config
        mock_current_config.messenger.type = MessengerType.SLACK

        # Setup new config with different type
        mock_new_config = Mock()
        mock_new_config.messenger.type = MessengerType.MATTERMOST
        mock_load_unified_config.return_value = mock_new_config

        result = reload_config()

        assert result is False
        mock_logger.warning.assert_called_with("Application type changed, keeping current configuration")

    @patch('app.config.config._config')
    @patch('app.config.config.load_unified_config')
    @patch('app.config.config.logger')
    def test_reload_config_validation_error(self, mock_logger, mock_load_unified_config,
                                            mock_current_config):
        """Test config reload with validation error."""
        mock_load_unified_config.side_effect = ConfigValidationError("Validation error")

        result = reload_config()

        assert result is False
        assert "Config validation failed, keeping current config" in mock_logger.warning.call_args[0][0]

    @patch('app.config.config._config')
    @patch('app.config.config.load_unified_config')
    @patch('app.config.config.logger')
    def test_reload_config_general_error(self, mock_logger, mock_load_unified_config,
                                         mock_current_config):
        """Test config reload with general error."""
        mock_load_unified_config.side_effect = Exception("General error")

        result = reload_config()

        assert result is False
        assert "Config reload failed, keeping current config" in mock_logger.warning.call_args[0][0]

    @patch('app.config.config._config')
    @patch('app.config.config.load_unified_config')
    def test_force_reload_config(self, mock_load_unified_config, mock_current_config, mock_unified_config):
        """Test force reload config."""
        mock_current_config.messenger.type = MessengerType.SLACK
        mock_unified_config.messenger.type = MessengerType.SLACK
        mock_load_unified_config.return_value = mock_unified_config

        result = reload_config()

        mock_load_unified_config.assert_called_once_with(exit_on_error=False)
        assert result is True
