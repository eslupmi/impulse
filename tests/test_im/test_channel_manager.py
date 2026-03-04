"""
Unit tests for app.im.channel_manager module.
"""
from unittest.mock import Mock, patch

import pytest

from app.im.channel_manager import ChannelManager


class TestChannelManager:
    """Test cases for ChannelManager class."""

    def setup_method(self):
        """Reset singleton instance before each test."""
        ChannelManager._instance = None

    def test_channel_manager_singleton(self):
        """Test that ChannelManager is a singleton."""
        manager1 = ChannelManager()
        manager2 = ChannelManager()

        assert manager1 is manager2
        assert manager1._initialized is True

    def test_channel_manager_initialization(self):
        """Test ChannelManager initialization."""
        manager = ChannelManager()

        assert manager._initialized is True
        assert manager._channels == {}

    def test_initialize_with_valid_channels(self):
        """Test initialize with valid channel configuration."""
        channels_list = ["channel1", "channel2"]
        channel1_mock = Mock()
        channel1_mock.id = "C123456789"
        channel1_mock.name = "Test Channel 1"
        channel2_mock = Mock()
        channel2_mock.id = "C987654321"
        channel2_mock.name = "Test Channel 2"

        channels_config = {
            "channel1": channel1_mock,
            "channel2": channel2_mock
        }
        default_channel = "default"

        with patch('app.im.channel_manager.logger') as mock_logger:
            manager = ChannelManager()
            result = manager.initialize(channels_list, channels_config, default_channel)

            # Check result structure
            assert len(result) == 2
            assert "channel1" in result
            assert "channel2" in result

            # Check channel data
            assert result["channel1"]["id"] == "C123456789"
            assert result["channel1"]["name"] == "Test Channel 1"
            assert result["channel2"]["id"] == "C987654321"
            assert result["channel2"]["name"] == "Test Channel 2"

            # Check internal channels storage
            assert len(manager._channels) == 2
            assert "C123456789" in manager._channels
            assert "C987654321" in manager._channels

    def test_initialize_with_undefined_channel(self):
        """Test initialize with undefined channel (uses default)."""
        channels_list = ["channel1", "undefined_channel"]
        channel1_mock = Mock()
        channel1_mock.id = "C123456789"
        channel1_mock.name = "Test Channel 1"
        default_mock = Mock()
        default_mock.id = "C999999999"
        default_mock.name = "Default Channel"

        channels_config = {
            "channel1": channel1_mock,
            "default": default_mock
        }
        default_channel = "default"

        with patch('app.im.channel_manager.logger') as mock_logger:
            manager = ChannelManager()
            result = manager.initialize(channels_list, channels_config, default_channel)

            # Check warning was logged
            mock_logger.warning.assert_called_once_with(
                'Channel not defined', extra={'channel': 'undefined_channel'}
            )

            # Check result structure
            assert len(result) == 2
            assert "channel1" in result
            assert "undefined_channel" in result

            # Check that undefined channel uses default
            assert result["undefined_channel"]["id"] == "C999999999"

    def test_initialize_with_missing_default_channel(self):
        """Test initialize when default channel is not found."""
        channels_list = ["channel1", "undefined_channel"]
        channels_config = {
            "channel1": Mock(id="C123456789", name="Test Channel 1")
        }
        default_channel = "missing_default"

        with patch('app.im.channel_manager.logger') as mock_logger:
            manager = ChannelManager()
            result = manager.initialize(channels_list, channels_config, default_channel)

            # Check error was logged
            mock_logger.error.assert_called_once_with(
                'Default channel not found in configuration',
                extra={'channel': 'missing_default'}
            )

            # Check that undefined channel uses default channel name as ID
            assert result["undefined_channel"]["id"] == "missing_default"

    def test_initialize_with_channel_no_id(self):
        """Test initialize with channel that has no ID."""
        channels_list = ["channel1", "no_id_channel"]
        channels_config = {
            "channel1": Mock(id="C123456789", name="Test Channel 1"),
            "no_id_channel": Mock(id=None, name="No ID Channel"),
            "default": Mock(id="C999999999", name="Default Channel")
        }
        default_channel = "default"

        with patch('app.im.channel_manager.logger') as mock_logger:
            manager = ChannelManager()
            result = manager.initialize(channels_list, channels_config, default_channel)

            # Check warning was logged
            mock_logger.warning.assert_called_once_with(
                "Channel has no `id`. Using default channel instead", extra={'channel': 'no_id_channel'}
            )

            # Check that no_id_channel uses default
            assert result["no_id_channel"]["id"] == "C999999999"

    def test_initialize_with_channel_no_id_and_missing_default(self):
        """Test initialize with channel that has no ID and default channel is not found."""
        channels_list = ["channel1", "no_id_channel"]
        channels_config = {
            "channel1": Mock(id="C123456789", name="Test Channel 1"),
            "no_id_channel": Mock(id=None, name="No ID Channel")
        }
        default_channel = "missing_default"

        with patch('app.im.channel_manager.logger') as mock_logger:
            manager = ChannelManager()
            result = manager.initialize(channels_list, channels_config, default_channel)

            # Check warning was logged for channel with no id
            mock_logger.warning.assert_any_call(
                "Channel has no `id`. Using default channel instead", extra={'channel': 'no_id_channel'}
            )
            # Check error was logged for missing default channel
            mock_logger.error.assert_called_with(
                'Default channel not found in configuration',
                extra={'channel': 'missing_default'}
            )

            # Check that no_id_channel uses channel name as ID
            assert result["no_id_channel"]["id"] == "no_id_channel"

    def test_initialize_with_dict_channel_config(self):
        """Test initialize with dictionary channel configuration."""
        channels_list = ["channel1"]
        channels_config = {
            "channel1": {"id": "C123456789", "name": "Test Channel 1"}
        }
        default_channel = "default"

        with patch('app.im.channel_manager.logger'):
            manager = ChannelManager()
            result = manager.initialize(channels_list, channels_config, default_channel)

            # Check result structure
            assert result["channel1"]["id"] == "C123456789"
            # Note: name is not copied from dict config, only from object config
            assert "name" not in result["channel1"]

    def test_get_channel_name_by_id_existing(self):
        """Test get_channel_name_by_id with existing channel."""
        channels_list = ["channel1"]
        channel1_mock = Mock()
        channel1_mock.id = "C123456789"
        channel1_mock.name = "Test Channel 1"

        channels_config = {
            "channel1": channel1_mock
        }
        default_channel = "default"

        with patch('app.im.channel_manager.logger'):
            manager = ChannelManager()
            manager.initialize(channels_list, channels_config, default_channel)

            # Test getting channel name by ID
            channel_name = manager.get_channel_name_by_id("C123456789")
            assert channel_name == "Test Channel 1"

    def test_get_channel_name_by_id_nonexistent(self):
        """Test get_channel_name_by_id with non-existent channel."""
        manager = ChannelManager()

        # Test getting channel name for non-existent ID
        channel_name = manager.get_channel_name_by_id("nonexistent")
        assert channel_name is None

    def test_get_channel_id_from_object(self):
        """Test _get_channel_id with channel object."""
        manager = ChannelManager()

        # Test with object that has id attribute
        channel_obj = Mock(id="C123456789")
        channel_id = manager._get_channel_id(channel_obj)
        assert channel_id == "C123456789"

    def test_get_channel_id_from_dict(self):
        """Test _get_channel_id with dictionary."""
        manager = ChannelManager()

        # Test with dictionary
        channel_dict = {"id": "C123456789"}
        channel_id = manager._get_channel_id(channel_dict)
        assert channel_id == "C123456789"

    def test_get_channel_id_from_invalid_object(self):
        """Test _get_channel_id with invalid object."""
        manager = ChannelManager()

        # Test with object that has no id attribute
        channel_obj = Mock(spec=[])  # Mock with no attributes
        channel_id = manager._get_channel_id(channel_obj)
        assert channel_id is None

    def test_initialize_clears_existing_channels(self):
        """Test that initialize clears existing channels."""
        # First initialization
        channels_list1 = ["channel1"]
        channels_config1 = {
            "channel1": Mock(id="C123456789", name="Test Channel 1")
        }
        default_channel = "default"

        with patch('app.im.channel_manager.logger'):
            manager = ChannelManager()
            manager.initialize(channels_list1, channels_config1, default_channel)

            # Check channels are set
            assert len(manager._channels) == 1
            assert "C123456789" in manager._channels

            # Second initialization with different channels
            channels_list2 = ["channel2"]
            channels_config2 = {
                "channel2": Mock(id="C987654321", name="Test Channel 2")
            }

            manager.initialize(channels_list2, channels_config2, default_channel)

            # Check that old channels are cleared
            assert len(manager._channels) == 1
            assert "C123456789" not in manager._channels
            assert "C987654321" in manager._channels
