"""
Unit tests for app.config.environment module.
"""
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.config.environment import EnvironmentConfig, get_environment_config
from tests.utils import create_mock_environment_config


class TestEnvironmentConfig:
    """Test cases for EnvironmentConfig class."""

    def test_default_values(self):
        """Test default values when no environment variables are set."""
        with patch.dict('os.environ', {}, clear=True):
            config = EnvironmentConfig()

        assert config.slack_bot_user_oauth_token == ""
        assert config.slack_verification_token == ""
        assert config.mattermost_access_token == ""
        assert config.telegram_bot_token == ""
        assert config.data_path == "./data"
        assert config.config_path == "./"
        assert config.provider_sync_interval == 60
        assert config.provider_max_events == 10
        assert config.provider_days_to_sync == 7
        assert config.provider_service_account_file == "./key.json"
        assert config.cors_allowed_origins == ["https://localhost:5000"]
        assert config.log_level == "INFO"
        assert config.http_prefix == ""
        assert config.listen_host == "0.0.0.0"
        assert config.listen_port == 5000
        assert config.http_proxy == ""
        assert config.proxy_url is None

    def test_environment_variable_loading(self):
        """Test loading values from environment variables."""
        env_vars = {
            'SLACK_BOT_USER_OAUTH_TOKEN': 'xoxb-test-token',
            'SLACK_VERIFICATION_TOKEN': 'test-verification',
            'MATTERMOST_ACCESS_TOKEN': 'mm-token',
            'TELEGRAM_BOT_TOKEN': 'tg-token',
            'DATA_PATH': '/custom/data',
            'CONFIG_PATH': '/custom/config',
            'CHAIN_PROVIDER_SYNC_INTERVAL_SECONDS': '300',
            'CHAIN_PROVIDER_MAX_EVENTS': '50',
            'CHAIN_PROVIDER_DAYS_TO_SYNC': '14',
            'GOOGLE_SERVICE_ACCOUNT_FILE': '/path/to/key.json',
            'CORS_ALLOWED_ORIGINS': 'https://localhost:3000,https://app.example.com',
            'LOG_LEVEL': 'DEBUG',
            'HTTP_PREFIX': '/api/v1',
            'LISTEN_HOST': '127.0.0.1',
            'LISTEN_PORT': '8080',
            'HTTP_PROXY': 'http://proxy.example.com:8080',
        }

        with patch.dict('os.environ', env_vars, clear=True):
            config = EnvironmentConfig()

        assert config.slack_bot_user_oauth_token == 'xoxb-test-token'
        assert config.slack_verification_token == 'test-verification'
        assert config.mattermost_access_token == 'mm-token'
        assert config.telegram_bot_token == 'tg-token'
        assert config.data_path == '/custom/data'
        assert config.config_path == '/custom/config'
        assert config.provider_sync_interval == 300
        assert config.provider_max_events == 50
        assert config.provider_days_to_sync == 14
        assert config.provider_service_account_file == '/path/to/key.json'
        assert config.cors_allowed_origins == ['https://localhost:3000', 'https://app.example.com']
        assert config.log_level == 'DEBUG'
        assert config.http_prefix == '/api/v1'
        assert config.listen_host == '127.0.0.1'
        assert config.listen_port == 8080
        assert config.http_proxy == 'http://proxy.example.com:8080'
        assert config.proxy_url == 'http://proxy.example.com:8080'

    def test_positive_integer_validation(self):
        """Test validation of positive integer fields."""
        # Test valid positive integers
        env_vars = {
            'CHAIN_PROVIDER_SYNC_INTERVAL_SECONDS': '300',
            'CHAIN_PROVIDER_MAX_EVENTS': '50',
            'CHAIN_PROVIDER_DAYS_TO_SYNC': '14',
            'LISTEN_PORT': '8080'
        }

        with patch.dict('os.environ', env_vars, clear=True):
            config = EnvironmentConfig()

        assert config.provider_sync_interval == 300
        assert config.provider_max_events == 50
        assert config.provider_days_to_sync == 14
        assert config.listen_port == 8080

    def test_positive_integer_validation_zero(self):
        """Test validation failure for zero values."""
        # Test with direct model creation (validation happens here)
        config_data = {
            'provider_sync_interval': 0,
            'provider_max_events': 0,
            'provider_days_to_sync': 0,
            'listen_port': 0
        }

        with pytest.raises(ValidationError, match="Configuration values must be positive integers"):
            EnvironmentConfig(**config_data)

    def test_positive_integer_validation_negative(self):
        """Test validation failure for negative values."""
        # Test with direct model creation (validation happens here)
        config_data = {
            'provider_sync_interval': -1,
            'provider_max_events': -5,
            'provider_days_to_sync': -10,
            'listen_port': -8080
        }

        with pytest.raises(ValidationError, match="Configuration values must be positive integers"):
            EnvironmentConfig(**config_data)

    def test_cors_origins_parsing(self):
        """Test CORS origins parsing and cleaning."""
        # Test with direct model creation to trigger validation
        config_data = {
            'cors_allowed_origins': [' https://localhost:3000 ', ' https://app.example.com ',
                                     ' https://api.example.com ']
        }

        config = EnvironmentConfig(**config_data)

        assert config.cors_allowed_origins == [
            'https://localhost:3000',
            'https://app.example.com',
            'https://api.example.com'
        ]

    def test_cors_origins_empty_values(self):
        """Test CORS origins with empty values."""
        # Test with direct model creation to trigger validation
        config_data = {
            'cors_allowed_origins': ['https://localhost:3000', '', 'https://app.example.com', ' ']
        }

        config = EnvironmentConfig(**config_data)

        # Should filter out empty values
        assert config.cors_allowed_origins == [
            'https://localhost:3000',
            'https://app.example.com'
        ]

    def test_cors_origins_single_value(self):
        """Test CORS origins with single value."""
        env_vars = {
            'CORS_ALLOWED_ORIGINS': 'https://app.example.com'
        }

        with patch.dict('os.environ', env_vars, clear=True):
            config = EnvironmentConfig()

        assert config.cors_allowed_origins == ['https://app.example.com']

    def test_incidents_path_property(self):
        """Test incidents_path property construction."""
        env_vars = {
            'DATA_PATH': '/custom/data'
        }

        with patch.dict('os.environ', env_vars, clear=True):
            config = EnvironmentConfig()

        assert config.incidents_path == '/custom/data/incidents'

    def test_config_file_path_property(self):
        """Test config_file_path property construction."""
        env_vars = {
            'CONFIG_PATH': '/custom/config'
        }

        with patch.dict('os.environ', env_vars, clear=True):
            config = EnvironmentConfig()

        assert config.config_file_path == '/custom/config/impulse.yml'

    def test_invalid_integer_values(self):
        """Test handling of invalid integer values."""
        env_vars = {
            'CHAIN_PROVIDER_SYNC_INTERVAL_SECONDS': 'not-a-number',
            'CHAIN_PROVIDER_MAX_EVENTS': 'also-not-a-number',
            'CHAIN_PROVIDER_DAYS_TO_SYNC': 'still-not-a-number',
            'LISTEN_PORT': 'definitely-not-a-number'
        }

        with patch.dict('os.environ', env_vars, clear=True):
            with pytest.raises(ValueError):
                EnvironmentConfig()

    def test_mixed_valid_invalid_integers(self):
        """Test mixed valid and invalid integer values."""
        env_vars = {
            'CHAIN_PROVIDER_SYNC_INTERVAL_SECONDS': '300',  # Valid
            'CHAIN_PROVIDER_MAX_EVENTS': 'invalid',  # Invalid
            'CHAIN_PROVIDER_DAYS_TO_SYNC': '14',  # Valid
            'LISTEN_PORT': '8080'  # Valid
        }

        with patch.dict('os.environ', env_vars, clear=True):
            with pytest.raises(ValueError):
                EnvironmentConfig()

    def test_field_descriptions(self):
        """Test that field descriptions are properly set."""
        # Check that fields have descriptions by examining the model class
        field_info = EnvironmentConfig.model_fields

        assert 'slack_bot_user_oauth_token' in field_info
        assert 'data_path' in field_info
        assert 'provider_sync_interval' in field_info
        assert 'cors_allowed_origins' in field_info
        assert 'http_prefix' in field_info

    def test_model_validation_with_custom_values(self):
        """Test model validation with custom values."""
        # Test with valid custom values
        config_data = {
            'slack_bot_user_oauth_token': 'xoxb-custom-token',
            'data_path': '/custom/data',
            'provider_sync_interval': 600,
            'provider_max_events': 100,
            'provider_days_to_sync': 30,
            'cors_allowed_origins': ['https://custom.com'],
            'log_level': 'WARNING',
            'http_prefix': '/custom/api',
            'listen_host': 'fake-host',
            'listen_port': 9000
        }

        config = EnvironmentConfig(**config_data)

        assert config.slack_bot_user_oauth_token == 'xoxb-custom-token'
        assert config.data_path == '/custom/data'
        assert config.provider_sync_interval == 600
        assert config.provider_max_events == 100
        assert config.provider_days_to_sync == 30
        assert config.cors_allowed_origins == ['https://custom.com']
        assert config.log_level == 'WARNING'
        assert config.http_prefix == '/custom/api'
        assert config.listen_host == 'fake-host'
        assert config.listen_port == 9000

    def test_model_validation_with_invalid_values(self):
        """Test model validation with invalid values."""
        config_data = {
            'provider_sync_interval': 0,  # Invalid: must be positive
            'provider_max_events': -1,  # Invalid: must be positive
            'provider_days_to_sync': 0,  # Invalid: must be positive
            'listen_port': -1  # Invalid: must be positive
        }

        with pytest.raises(ValidationError, match="Configuration values must be positive integers"):
            EnvironmentConfig(**config_data)

    def test_log_level_validation_valid_levels(self):
        """Test log level validation with valid levels."""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

        for level in valid_levels:
            config_data = {'log_level': level}
            config = EnvironmentConfig(**config_data)
            assert config.log_level == level

    def test_log_level_validation_case_insensitive(self):
        """Test log level validation is case insensitive."""
        test_cases = [
            ('debug', 'DEBUG'),
            ('info', 'INFO'),
            ('warning', 'WARNING'),
            ('error', 'ERROR'),
            ('critical', 'CRITICAL'),
            ('Debug', 'DEBUG'),
            ('Info', 'INFO')
        ]

        for input_level, expected_level in test_cases:
            config_data = {'log_level': input_level}
            config = EnvironmentConfig(**config_data)
            assert config.log_level == expected_level

    def test_log_level_validation_invalid_level(self):
        """Test log level validation with invalid level."""
        config_data = {'log_level': 'INVALID_LEVEL'}

        with pytest.raises(ValidationError, match="Log level must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL"):
            EnvironmentConfig(**config_data)

    def test_http_prefix_validation_valid_prefixes(self):
        """Test HTTP prefix validation with valid prefixes."""
        valid_prefixes = ['', '/api', '/impulse', '/v1/api']

        for prefix in valid_prefixes:
            config_data = {'http_prefix': prefix}
            config = EnvironmentConfig(**config_data)
            assert config.http_prefix == prefix

    def test_http_prefix_validation_must_start_with_slash(self):
        """Test HTTP prefix validation must start with slash."""
        config_data = {'http_prefix': 'api'}  # Missing leading slash

        with pytest.raises(ValidationError, match="HTTP prefix must start with '/' \\(e.g., '/impulse'\\)"):
            EnvironmentConfig(**config_data)

    def test_http_prefix_validation_cannot_end_with_slash(self):
        """Test HTTP prefix validation cannot end with slash."""
        config_data = {'http_prefix': '/api/'}  # Ends with slash

        with pytest.raises(ValidationError,
                           match="HTTP prefix must not end with '/' \\(e.g., '/impulse' not '/impulse/'\\)"):
            EnvironmentConfig(**config_data)

    def test_proxy_url_from_http_proxy(self):
        with patch.dict('os.environ', {'HTTP_PROXY': 'http://proxy.example.com:8080'}, clear=True):
            config = EnvironmentConfig()

        assert config.http_proxy == 'http://proxy.example.com:8080'
        assert config.proxy_url == 'http://proxy.example.com:8080'

    def test_proxy_url_none_when_unset(self):
        with patch.dict('os.environ', {}, clear=True):
            config = EnvironmentConfig()

        assert config.proxy_url is None


class TestEnvironmentConfigFunctions:
    """Test cases for environment configuration functions."""
