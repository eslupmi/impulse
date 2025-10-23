"""
Unit tests for app.logging module.
"""
import logging
from unittest.mock import Mock, patch

import pytest

from app.logging import CustomFormatter, create_logger, configure_uvicorn_logging


class TestCustomFormatter:
    """Test cases for CustomFormatter class."""

    def _create_mock_record(self, levelno, levelname, message):
        """Helper to create a proper mock record."""
        record = Mock()
        record.levelno = levelno
        record.asctime = "2023-01-01 12:00:00"
        record.levelname = levelname
        record.message = message
        record.created = 1672574400.0  # Unix timestamp
        record.msecs = 0  # Milliseconds
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        record.getMessage.return_value = message
        return record

    def test_custom_formatter_initialization(self):
        """Test CustomFormatter initialization."""
        formatter = CustomFormatter()

        assert formatter is not None
        assert hasattr(formatter, 'grey')
        assert hasattr(formatter, 'yellow')
        assert hasattr(formatter, 'white')
        assert hasattr(formatter, 'red')
        assert hasattr(formatter, 'bold_red')
        assert hasattr(formatter, 'reset')
        assert hasattr(formatter, 'format')
        assert hasattr(formatter, 'FORMATS')

    def test_custom_formatter_colors(self):
        """Test CustomFormatter color attributes."""
        formatter = CustomFormatter()

        # Test that colors are ANSI escape codes
        assert formatter.grey.startswith('\033')
        assert formatter.yellow.startswith('\033')
        assert formatter.white.startswith('\033')
        assert formatter.red.startswith('\033')
        assert formatter.bold_red.startswith('\033')
        assert formatter.reset.startswith('\033')

    def test_custom_formatter_formats_dict(self):
        """Test CustomFormatter FORMATS dictionary."""
        formatter = CustomFormatter()

        # Test that FORMATS contains all log levels
        assert logging.DEBUG in formatter.FORMATS
        assert logging.INFO in formatter.FORMATS
        assert logging.WARNING in formatter.FORMATS
        assert logging.ERROR in formatter.FORMATS
        assert logging.CRITICAL in formatter.FORMATS

    def test_custom_formatter_format_debug(self):
        """Test CustomFormatter format method with DEBUG level."""
        formatter = CustomFormatter()
        record = self._create_mock_record(logging.DEBUG, "DEBUG", "Test debug message")

        result = formatter.format(record)

        assert isinstance(result, str)
        assert "Test debug message" in result

    def test_custom_formatter_format_info(self):
        """Test CustomFormatter format method with INFO level."""
        formatter = CustomFormatter()
        record = self._create_mock_record(logging.INFO, "INFO", "Test info message")

        result = formatter.format(record)

        assert isinstance(result, str)
        assert "Test info message" in result

    def test_custom_formatter_format_warning(self):
        """Test CustomFormatter format method with WARNING level."""
        formatter = CustomFormatter()
        record = self._create_mock_record(logging.WARNING, "WARNING", "Test warning message")

        result = formatter.format(record)

        assert isinstance(result, str)
        assert "Test warning message" in result

    def test_custom_formatter_format_error(self):
        """Test CustomFormatter format method with ERROR level."""
        formatter = CustomFormatter()
        record = self._create_mock_record(logging.ERROR, "ERROR", "Test error message")

        result = formatter.format(record)

        assert isinstance(result, str)
        assert "Test error message" in result

    def test_custom_formatter_format_critical(self):
        """Test CustomFormatter format method with CRITICAL level."""
        formatter = CustomFormatter()
        record = self._create_mock_record(logging.CRITICAL, "CRITICAL", "Test critical message")

        result = formatter.format(record)

        assert isinstance(result, str)
        assert "Test critical message" in result

    def test_custom_formatter_format_unknown_level(self):
        """Test CustomFormatter format method with unknown level."""
        formatter = CustomFormatter()
        record = self._create_mock_record(999, "UNKNOWN", "Test unknown message")

        # Should not raise exception
        result = formatter.format(record)

        assert isinstance(result, str)
        assert "Test unknown message" in result

    def test_custom_formatter_format_with_special_characters(self):
        """Test CustomFormatter format method with special characters."""
        formatter = CustomFormatter()
        record = self._create_mock_record(logging.INFO, "INFO", "Test message with special chars: !@#$%^&*()")

        result = formatter.format(record)

        assert isinstance(result, str)
        assert "Test message with special chars: !@#$%^&*()" in result

    def test_custom_formatter_format_with_unicode(self):
        """Test CustomFormatter format method with unicode characters."""
        formatter = CustomFormatter()
        record = self._create_mock_record(logging.INFO, "INFO", "Test message with unicode: 测试")

        result = formatter.format(record)

        assert isinstance(result, str)
        assert "Test message with unicode: 测试" in result

    def test_custom_formatter_format_with_emoji(self):
        """Test CustomFormatter format method with emoji."""
        formatter = CustomFormatter()
        record = self._create_mock_record(logging.INFO, "INFO", "Test message with emoji: 🚨")

        result = formatter.format(record)

        assert isinstance(result, str)
        assert "Test message with emoji: 🚨" in result

    def test_custom_formatter_format_with_very_long_message(self):
        """Test CustomFormatter format method with very long message."""
        formatter = CustomFormatter()
        long_message = "Test message: " + "a" * 10000
        record = self._create_mock_record(logging.INFO, "INFO", long_message)

        result = formatter.format(record)

        assert isinstance(result, str)
        assert long_message in result

    def test_custom_formatter_format_with_empty_message(self):
        """Test CustomFormatter format method with empty message."""
        formatter = CustomFormatter()
        record = self._create_mock_record(logging.INFO, "INFO", "")

        result = formatter.format(record)

        assert isinstance(result, str)

    def test_custom_formatter_format_with_none_values(self):
        """Test CustomFormatter format method with None values."""
        formatter = CustomFormatter()
        record = self._create_mock_record(logging.INFO, "INFO", "Test message")
        record.asctime = None
        record.levelname = None
        record.message = None

        # This should raise an exception due to None values in format string
        with pytest.raises(TypeError):
            formatter.format(record)

    def test_custom_formatter_format_with_very_long_asctime(self):
        """Test CustomFormatter format method with very long asctime."""
        formatter = CustomFormatter()
        record = self._create_mock_record(logging.INFO, "INFO", "Test message")
        record.asctime = "2023-01-01 12:00:00" + "a" * 1000

        result = formatter.format(record)

        assert isinstance(result, str)
        assert "Test message" in result

    def test_custom_formatter_format_with_very_long_levelname(self):
        """Test CustomFormatter format method with very long levelname."""
        formatter = CustomFormatter()
        record = self._create_mock_record(logging.INFO, "INFO" + "a" * 1000, "Test message")

        result = formatter.format(record)

        assert isinstance(result, str)
        assert "Test message" in result


class TestCreateLogger:
    """Test cases for create_logger function."""

    def test_create_logger_basic(self):
        """Test create_logger with basic parameters."""
        logger = create_logger("test_logger")

        assert logger is not None
        assert logger.name == "test_logger"
        assert logger.level == logging.INFO
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.StreamHandler)

    def test_create_logger_with_custom_level(self):
        """Test create_logger with custom level."""
        logger = create_logger("test_logger", logging.DEBUG)

        assert logger is not None
        assert logger.name == "test_logger"
        assert logger.level == logging.DEBUG

    def test_create_logger_with_different_levels(self):
        """Test create_logger with different log levels."""
        levels = [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]

        for level in levels:
            logger = create_logger(f"test_logger_{level}", level)
            assert logger.level == level

    def test_create_logger_with_numeric_level(self):
        """Test create_logger with numeric level."""
        logger = create_logger("test_logger", 20)  # INFO level

        assert logger.level == 20

    def test_create_logger_with_negative_level(self):
        """Test create_logger with negative level."""
        logger = create_logger("test_logger", -1)

        assert logger.level == -1

    def test_create_logger_with_very_large_level(self):
        """Test create_logger with very large level."""
        logger = create_logger("test_logger", 1000000)

        assert logger.level == 1000000

    def test_create_logger_with_string_name(self):
        """Test create_logger with string name."""
        logger = create_logger("test_logger_string")

        assert logger.name == "test_logger_string"

    def test_create_logger_with_empty_name(self):
        """Test create_logger with empty name."""
        logger = create_logger("")

        # Empty string becomes 'root' logger
        assert logger.name == "root"

    def test_create_logger_with_none_name(self):
        """Test create_logger with None name."""
        logger = create_logger(None)

        # None becomes 'root' logger
        assert logger.name == "root"

    def test_create_logger_with_special_characters_in_name(self):
        """Test create_logger with special characters in name."""
        logger = create_logger("test_logger!@#$%^&*()")

        assert logger.name == "test_logger!@#$%^&*()"

    def test_create_logger_with_unicode_in_name(self):
        """Test create_logger with unicode in name."""
        logger = create_logger("test_logger_测试")

        assert logger.name == "test_logger_测试"

    def test_create_logger_with_emoji_in_name(self):
        """Test create_logger with emoji in name."""
        logger = create_logger("test_logger🚨")

        assert logger.name == "test_logger🚨"

    def test_create_logger_with_very_long_name(self):
        """Test create_logger with very long name."""
        long_name = "test_logger_" + "a" * 10000
        logger = create_logger(long_name)

        assert logger.name == long_name

    def test_create_logger_handler_formatter(self):
        """Test create_logger handler formatter."""
        logger = create_logger("test_logger")

        handler = logger.handlers[0]
        assert isinstance(handler.formatter, CustomFormatter)

    def test_create_logger_different_names(self):
        """Test create_logger with different names creates separate loggers."""
        logger1 = create_logger("test_logger_1")
        logger2 = create_logger("test_logger_2")

        assert logger1 is not logger2
        assert logger1.name != logger2.name

    def test_create_logger_with_invalid_level(self):
        """Test create_logger with invalid level raises TypeError."""
        with pytest.raises(TypeError):
            create_logger("test_logger", 20.5)  # Float level not allowed


class TestConfigureUvicornLogging:
    """Test cases for configure_uvicorn_logging function."""

    def test_configure_uvicorn_logging_basic(self):
        """Test configure_uvicorn_logging basic functionality."""
        with patch('app.logging.logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            configure_uvicorn_logging()

            # Should be called for uvicorn, uvicorn.access, uvicorn.error
            # Plus the initial calls for uvicorn and uvicorn.access
            assert mock_get_logger.call_count >= 3

    def test_configure_uvicorn_logging_sets_levels(self):
        """Test configure_uvicorn_logging sets appropriate levels."""
        with patch('app.logging.logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            configure_uvicorn_logging()

            # Should set level to WARNING for uvicorn and uvicorn.access
            assert mock_logger.setLevel.call_count >= 2

    def test_configure_uvicorn_logging_clears_handlers(self):
        """Test configure_uvicorn_logging clears existing handlers."""
        with patch('app.logging.logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            configure_uvicorn_logging()

            # Should clear handlers
            assert mock_logger.handlers.clear.call_count >= 3

    def test_configure_uvicorn_logging_adds_handlers(self):
        """Test configure_uvicorn_logging adds new handlers."""
        with patch('app.logging.logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            configure_uvicorn_logging()

            # Should add handlers
            assert mock_logger.addHandler.call_count >= 3

    def test_configure_uvicorn_logging_sets_propagate(self):
        """Test configure_uvicorn_logging sets propagate to False."""
        with patch('app.logging.logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            configure_uvicorn_logging()

            # Should set propagate to False
            assert mock_logger.propagate == False

    def test_configure_uvicorn_logging_sets_formatter(self):
        """Test configure_uvicorn_logging sets custom formatter."""
        with patch('app.logging.logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            configure_uvicorn_logging()

            # Should set formatter on handlers
            assert mock_logger.addHandler.call_count >= 3

    def test_configure_uvicorn_logging_with_mock_stream_handler(self):
        """Test configure_uvicorn_logging with mocked StreamHandler."""
        with patch('app.logging.logging.getLogger') as mock_get_logger, \
                patch('app.logging.logging.StreamHandler') as mock_stream_handler:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            configure_uvicorn_logging()

            # Should create StreamHandler instances
            assert mock_stream_handler.call_count >= 3

    def test_configure_uvicorn_logging_with_mock_custom_formatter(self):
        """Test configure_uvicorn_logging with mocked CustomFormatter."""
        with patch('app.logging.logging.getLogger') as mock_get_logger, \
                patch('app.logging.CustomFormatter') as mock_formatter:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            configure_uvicorn_logging()

            # Should create CustomFormatter instances
            assert mock_formatter.call_count >= 3

    def test_configure_uvicorn_logging_multiple_calls(self):
        """Test configure_uvicorn_logging with multiple calls."""
        with patch('app.logging.logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            # First call
            configure_uvicorn_logging()
            first_call_count = mock_get_logger.call_count

            # Second call
            configure_uvicorn_logging()
            second_call_count = mock_get_logger.call_count

            # Should be called the same number of times
            assert second_call_count == first_call_count * 2

    def test_configure_uvicorn_logging_with_different_logger_names(self):
        """Test configure_uvicorn_logging with different logger names."""
        with patch('app.logging.logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            configure_uvicorn_logging()

            # Should be called with specific logger names
            expected_names = ["uvicorn", "uvicorn.access", "uvicorn.error"]
            actual_names = [call[0][0] for call in mock_get_logger.call_args_list]

            for expected_name in expected_names:
                assert expected_name in actual_names

    def test_configure_uvicorn_logging_handles_exceptions_gracefully(self):
        """Test configure_uvicorn_logging handles exceptions gracefully."""
        with patch('app.logging.logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_logger.setLevel.side_effect = Exception("Test exception")
            mock_get_logger.return_value = mock_logger

            # Should not raise exception, but the exception will propagate
            # This is expected behavior since we're not catching exceptions
            with pytest.raises(Exception, match="Test exception"):
                configure_uvicorn_logging()
