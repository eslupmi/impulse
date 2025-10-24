"""
Unit tests for app.im.helpers module.
"""
from unittest.mock import Mock, patch

import pytest

from app.im.helpers import get_application


class TestGetApplication:
    """Test cases for get_application function."""

    def test_get_application_slack(self):
        """Test get_application returns SlackApplication for slack type."""
        mock_config = Mock()
        mock_config.type = 'slack'
        channels = Mock()
        default_channel = Mock()
        
        with patch('app.im.helpers.SlackApplication') as mock_slack_app:
            result = get_application(mock_config, channels, default_channel)
            
            mock_slack_app.assert_called_once_with(mock_config, channels, default_channel)
            assert result == mock_slack_app.return_value

    def test_get_application_mattermost(self):
        """Test get_application returns MattermostApplication for mattermost type."""
        mock_config = Mock()
        mock_config.type = 'mattermost'
        channels = Mock()
        default_channel = Mock()
        
        with patch('app.im.helpers.MattermostApplication') as mock_mattermost_app:
            result = get_application(mock_config, channels, default_channel)
            
            mock_mattermost_app.assert_called_once_with(mock_config, channels, default_channel)
            assert result == mock_mattermost_app.return_value

    def test_get_application_telegram(self):
        """Test get_application returns TelegramApplication for telegram type."""
        mock_config = Mock()
        mock_config.type = 'telegram'
        channels = Mock()
        default_channel = Mock()
        
        with patch('app.im.helpers.TelegramApplication') as mock_telegram_app:
            result = get_application(mock_config, channels, default_channel)
            
            mock_telegram_app.assert_called_once_with(mock_config, channels, default_channel)
            assert result == mock_telegram_app.return_value

    def test_get_application_none(self):
        """Test get_application returns NullApplication for none type."""
        mock_config = Mock()
        mock_config.type = 'none'
        channels = Mock()
        default_channel = Mock()
        
        with patch('app.im.helpers.NullApplication') as mock_null_app:
            result = get_application(mock_config, channels, default_channel)
            
            mock_null_app.assert_called_once_with(mock_config, channels, default_channel)
            assert result == mock_null_app.return_value

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
        
        with pytest.raises(ValueError, match="Unknown application type: None"):
            get_application(mock_config, channels, default_channel)
