"""
Unit tests for app.im.helpers module.
"""
from types import MappingProxyType
from unittest.mock import Mock, patch

import pytest

from app.im.helpers import get_application


class TestGetApplication:
    """Test cases for get_application function."""

    @pytest.mark.parametrize('provider_id', ['slack', 'mattermost', 'telegram', 'none'])
    def test_get_application_uses_registry_and_composed_facade(self, provider_id):
        config = Mock(type=provider_id)
        channels = {'default': {'id': 'C1'}}
        registration = Mock()
        registry = Mock()
        registry.resolve.return_value = registration
        environment = Mock(dev_messenger_custom_address=None)
        with patch('app.im.helpers.get_provider_registry', return_value=registry), \
                patch('app.im.helpers.get_environment_config', return_value=environment), \
                patch('app.im.helpers.Application') as facade:
            result = get_application(config, channels, 'default')
        registry.resolve.assert_called_once_with(provider_id)
        called_config, secrets = registration.factory.call_args.args
        assert called_config is config
        assert isinstance(secrets, MappingProxyType)
        facade.assert_called_once_with(
            config, channels, 'default', webhooks=None,
            provider=registration.factory.return_value,
        )
        assert result is facade.return_value

    def test_get_application_unknown_type(self):
        """Test get_application raises ValueError for unknown type."""
        mock_config = Mock()
        mock_config.type = 'unknown'
        channels = Mock()
        default_channel = Mock()

        with pytest.raises(ValueError, match="Unknown application type: unknown"):
            get_application(mock_config, channels, default_channel)

    def test_get_application_empty_type(self):
        """Test get_application raises ValueError for empty type."""
        mock_config = Mock()
        mock_config.type = ''
        channels = Mock()
        default_channel = Mock()

        with pytest.raises(ValueError, match="Unknown application type: "):
            get_application(mock_config, channels, default_channel)

    def test_get_application_none_type(self):
        """Test get_application raises ValueError for None type."""
        mock_config = Mock()
        mock_config.type = None
        channels = Mock()
        default_channel = Mock()

        with pytest.raises(ValueError, match="Invalid messenger provider ID: expected a string"):
            get_application(mock_config, channels, default_channel)
