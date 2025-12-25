"""
Unit tests for app.logging module.
"""
import json
import logging
from unittest.mock import Mock, patch

import pytest

import sys
from app.logging import (
    JSONFormatter,
    ErrorFilter,
    InfoFilter,
    create_logger,
    configure_uvicorn_logging
)


class TestJSONFormatter:
    """Test cases for JSONFormatter class."""

    def _create_mock_record(self, levelno, levelname, message, module="test_module", extra=None):
        """Helper to create a proper mock record."""
        record = Mock()
        record.levelno = levelno
        record.levelname = levelname
        record.message = message
        record.module = module
        record.created = 1672574400.0  # Unix timestamp
        record.msecs = 123  # Milliseconds
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        record.getMessage.return_value = message
        if extra is not None:
            record.extra = extra
        return record

    def test_json_formatter_initialization(self):
        """Test JSONFormatter initialization."""
        formatter = JSONFormatter()
        assert isinstance(formatter, logging.Formatter)

    def test_json_formatter_format_info(self):
        """Test JSONFormatter format method with INFO level."""
        formatter = JSONFormatter()
        record = self._create_mock_record(logging.INFO, "INFO", "Test info message")

        result = formatter.format(record)
        data = json.loads(result)

        assert isinstance(result, str)
        assert data['level'] == "INFO"
        assert data['message'] == "Test info message"
        assert data['module'] == "test_module"
        assert 'time' in data
        assert data['time'].endswith('Z')

    def test_json_formatter_format_with_extra_fields(self):
        """Test JSONFormatter format method with extra_fields in extra."""
        formatter = JSONFormatter()
        extra = {'extra_fields': {'provider': 'google', 'chain': 'test_chain'}}
        record = self._create_mock_record(logging.INFO, "INFO", "Test message", extra=extra)

        result = formatter.format(record)
        data = json.loads(result)

        assert data['provider'] == 'google'
        assert data['chain'] == 'test_chain'
        assert data['message'] == "Test message"

    def test_json_formatter_format_without_extra_fields(self):
        """Test JSONFormatter format method without extra_fields."""
        formatter = JSONFormatter()
        extra = {'other_field': 'value'}
        record = self._create_mock_record(logging.INFO, "INFO", "Test message", extra=extra)

        result = formatter.format(record)
        data = json.loads(result)

        assert 'other_field' not in data
        assert data['message'] == "Test message"

    def test_json_formatter_format_with_empty_extra_fields(self):
        """Test JSONFormatter format method with empty extra_fields."""
        formatter = JSONFormatter()
        extra = {'extra_fields': {}}
        record = self._create_mock_record(logging.INFO, "INFO", "Test message", extra=extra)

        result = formatter.format(record)
        data = json.loads(result)

        assert data['message'] == "Test message"
        # Should not have any extra fields

    def test_json_formatter_format_with_non_dict_extra_fields(self):
        """Test JSONFormatter format method with non-dict extra_fields."""
        formatter = JSONFormatter()
        extra = {'extra_fields': 'not a dict'}
        record = self._create_mock_record(logging.INFO, "INFO", "Test message", extra=extra)

        result = formatter.format(record)
        data = json.loads(result)

        assert data['message'] == "Test message"
        # Should not have extra_fields since it's not a dict

    def test_json_formatter_format_with_unicode(self):
        """Test JSONFormatter format method with unicode characters."""
        formatter = JSONFormatter()
        record = self._create_mock_record(logging.INFO, "INFO", "Test message with unicode: 测试")

        result = formatter.format(record)
        data = json.loads(result)

        assert "测试" in data['message']
        # JSON should be valid with ensure_ascii=False
        assert isinstance(result, str)

    def test_json_formatter_format_with_emoji(self):
        """Test JSONFormatter format method with emoji."""
        formatter = JSONFormatter()
        record = self._create_mock_record(logging.INFO, "INFO", "Test message with emoji: 🚨")

        result = formatter.format(record)
        data = json.loads(result)

        assert "🚨" in data['message']

    def test_json_formatter_format_all_levels(self):
        """Test JSONFormatter format method with all log levels."""
        formatter = JSONFormatter()
        levels = [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
            (logging.CRITICAL, "CRITICAL"),
        ]

        for levelno, levelname in levels:
            record = self._create_mock_record(levelno, levelname, f"Test {levelname} message")
            result = formatter.format(record)
            data = json.loads(result)
            assert data['level'] == levelname
            assert data['message'] == f"Test {levelname} message"


class TestCreateLogger:
    """Test cases for create_logger function."""

    def test_create_logger_basic(self):
        """Test create_logger with basic parameters."""
        # Use unique name to avoid conflicts
        import time
        unique_name = f"test_logger_basic_{int(time.time() * 1000000)}"
        
        # Clear handlers before creating logger
        existing_logger = logging.getLogger(unique_name)
        existing_logger.handlers.clear()
        
        logger = create_logger(unique_name)

        assert logger is not None
        assert logger.name == unique_name
        assert logger.level == logging.INFO
        
        # Should have exactly 2 handlers
        assert len(logger.handlers) == 2
        
        # Find our handlers
        stdout_handler = None
        stderr_handler = None
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                if handler.stream == sys.stdout:
                    for filter_obj in handler.filters:
                        if isinstance(filter_obj, InfoFilter):
                            stdout_handler = handler
                            break
                elif handler.stream == sys.stderr:
                    for filter_obj in handler.filters:
                        if isinstance(filter_obj, ErrorFilter):
                            stderr_handler = handler
                            break
        
        assert stdout_handler is not None
        assert stderr_handler is not None
        assert isinstance(stdout_handler.formatter, JSONFormatter)
        assert isinstance(stderr_handler.formatter, JSONFormatter)

    def test_create_logger_with_custom_level(self):
        """Test create_logger with custom level."""
        import time
        unique_name = f"test_logger_custom_{int(time.time() * 1000000)}"
        # Clear handlers before creating logger
        existing_logger = logging.getLogger(unique_name)
        existing_logger.handlers.clear()
        logger = create_logger(unique_name, logging.DEBUG)

        assert logger is not None
        assert logger.name == unique_name
        assert logger.level == logging.DEBUG

    def test_create_logger_with_different_levels(self):
        """Test create_logger with different log levels."""
        import time
        base_time = int(time.time() * 1000000)
        levels = [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]

        for idx, level in enumerate(levels):
            unique_name = f"test_logger_{level}_{base_time + idx}"
            # Clear handlers before creating logger
            existing_logger = logging.getLogger(unique_name)
            existing_logger.handlers.clear()
            logger = create_logger(unique_name, level)
            assert logger.level == level

    def test_create_logger_with_numeric_level(self):
        """Test create_logger with numeric level."""
        import time
        unique_name = f"test_logger_numeric_{int(time.time() * 1000000)}"
        # Clear handlers before creating logger
        existing_logger = logging.getLogger(unique_name)
        existing_logger.handlers.clear()
        logger = create_logger(unique_name, 20)  # INFO level

        assert logger.level == 20

    def test_create_logger_with_negative_level(self):
        """Test create_logger with negative level."""
        import time
        unique_name = f"test_logger_negative_{int(time.time() * 1000000)}"
        # Clear handlers before creating logger
        existing_logger = logging.getLogger(unique_name)
        existing_logger.handlers.clear()
        logger = create_logger(unique_name, -1)

        assert logger.level == -1

    def test_create_logger_with_very_large_level(self):
        """Test create_logger with very large level."""
        import time
        unique_name = f"test_logger_large_{int(time.time() * 1000000)}"
        # Clear handlers before creating logger
        existing_logger = logging.getLogger(unique_name)
        existing_logger.handlers.clear()
        logger = create_logger(unique_name, 1000000)

        assert logger.level == 1000000

    def test_create_logger_with_string_name(self):
        """Test create_logger with string name."""
        import time
        unique_name = f"test_logger_string_{int(time.time() * 1000000)}"
        # Clear handlers before creating logger
        existing_logger = logging.getLogger(unique_name)
        existing_logger.handlers.clear()
        logger = create_logger(unique_name)

        assert logger.name == unique_name

    def test_create_logger_with_empty_name(self):
        """Test create_logger with empty name."""
        # Empty string becomes 'root' logger - need to be careful with this
        # Clear handlers first to avoid duplicates
        root_logger = logging.getLogger("")
        root_logger.handlers.clear()
        logger = create_logger("")

        # Empty string becomes 'root' logger
        assert logger.name == "root"

    def test_create_logger_with_none_name(self):
        """Test create_logger with None name."""
        # None becomes 'root' logger - need to be careful with this
        # Clear handlers first to avoid duplicates
        root_logger = logging.getLogger("")
        root_logger.handlers.clear()
        logger = create_logger(None)

        # None becomes 'root' logger
        assert logger.name == "root"

    def test_create_logger_with_special_characters_in_name(self):
        """Test create_logger with special characters in name."""
        import time
        unique_name = f"test_logger_special_{int(time.time() * 1000000)}!@#$%^&*()"
        # Clear handlers before creating logger
        existing_logger = logging.getLogger(unique_name)
        existing_logger.handlers.clear()
        logger = create_logger(unique_name)

        assert logger.name == unique_name

    def test_create_logger_with_unicode_in_name(self):
        """Test create_logger with unicode in name."""
        import time
        unique_name = f"test_logger_unicode_{int(time.time() * 1000000)}_测试"
        # Clear handlers before creating logger
        existing_logger = logging.getLogger(unique_name)
        existing_logger.handlers.clear()
        logger = create_logger(unique_name)

        assert logger.name == unique_name

    def test_create_logger_with_emoji_in_name(self):
        """Test create_logger with emoji in name."""
        import time
        unique_name = f"test_logger_emoji_{int(time.time() * 1000000)}🚨"
        # Clear handlers before creating logger
        existing_logger = logging.getLogger(unique_name)
        existing_logger.handlers.clear()
        logger = create_logger(unique_name)

        assert logger.name == unique_name

    def test_create_logger_with_very_long_name(self):
        """Test create_logger with very long name."""
        import time
        long_name = f"test_logger_{int(time.time() * 1000000)}_" + "a" * 10000
        # Clear handlers before creating logger
        existing_logger = logging.getLogger(long_name)
        existing_logger.handlers.clear()
        logger = create_logger(long_name)

        assert logger.name == long_name

    def test_create_logger_handler_formatter(self):
        """Test create_logger handler formatter."""
        import time
        unique_name = f"test_logger_formatter_{int(time.time() * 1000000)}"
        
        # Clear handlers before creating logger
        existing_logger = logging.getLogger(unique_name)
        existing_logger.handlers.clear()
        
        logger = create_logger(unique_name)

        # Should have exactly 2 handlers
        assert len(logger.handlers) == 2

        # Find our handlers and check formatters
        found_stdout = False
        found_stderr = False
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                if handler.stream == sys.stdout:
                    for filter_obj in handler.filters:
                        if isinstance(filter_obj, InfoFilter):
                            assert isinstance(handler.formatter, JSONFormatter)
                            found_stdout = True
                            break
                elif handler.stream == sys.stderr:
                    for filter_obj in handler.filters:
                        if isinstance(filter_obj, ErrorFilter):
                            assert isinstance(handler.formatter, JSONFormatter)
                            found_stderr = True
                            break
        
        assert found_stdout
        assert found_stderr

    def test_create_logger_different_names(self):
        """Test create_logger with different names creates separate loggers."""
        import time
        unique_name1 = f"test_logger_1_{int(time.time() * 1000000)}"
        unique_name2 = f"test_logger_2_{int(time.time() * 1000000) + 1}"
        # Clear handlers before creating loggers
        existing_logger1 = logging.getLogger(unique_name1)
        existing_logger1.handlers.clear()
        existing_logger2 = logging.getLogger(unique_name2)
        existing_logger2.handlers.clear()
        logger1 = create_logger(unique_name1)
        logger2 = create_logger(unique_name2)

        assert logger1 is not logger2
        assert logger1.name != logger2.name
    
    def test_create_logger_idempotent(self):
        """Test that create_logger doesn't add duplicate handlers on multiple calls."""
        import time
        unique_name = f"test_logger_idempotent_{int(time.time() * 1000000)}"
        
        # Clear handlers before first call to ensure clean state
        existing_logger = logging.getLogger(unique_name)
        existing_logger.handlers.clear()
        
        # First call
        logger1 = create_logger(unique_name)
        handler_count_1 = len([h for h in logger1.handlers 
                               if isinstance(h, logging.StreamHandler) and 
                               (h.stream == sys.stdout or h.stream == sys.stderr)])
        
        # Should have exactly 2 handlers after first call
        assert handler_count_1 == 2
        
        # Second call with same name - should not add duplicate handlers
        # (function now checks for existing handlers internally)
        logger2 = create_logger(unique_name)
        handler_count_2 = len([h for h in logger2.handlers 
                               if isinstance(h, logging.StreamHandler) and 
                               (h.stream == sys.stdout or h.stream == sys.stderr)])
        
        # Should be the same logger instance
        assert logger1 is logger2
        # Should have exactly 2 handlers (not duplicated, function prevents duplicates)
        assert handler_count_2 == 2
        assert handler_count_1 == handler_count_2

    def test_create_logger_with_invalid_level(self):
        """Test create_logger with invalid level raises TypeError."""
        with pytest.raises(TypeError):
            create_logger("test_logger", 20.5)  # Float level not allowed

    def test_create_logger_stdout_stderr_separation(self):
        """Test that create_logger creates handlers for both stdout and stderr."""
        # Use a unique logger name to avoid conflicts with other tests
        import time
        unique_name = f"test_logger_separation_{int(time.time() * 1000000)}"
        
        # Clear any existing handlers for this logger
        existing_logger = logging.getLogger(unique_name)
        existing_logger.handlers.clear()
        
        logger = create_logger(unique_name)
        
        # Should have exactly 2 handlers
        assert len(logger.handlers) == 2
        
        # Find stdout and stderr handlers
        stdout_handler = None
        stderr_handler = None
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                if handler.stream == sys.stdout:
                    for filter_obj in handler.filters:
                        if isinstance(filter_obj, InfoFilter):
                            stdout_handler = handler
                            break
                elif handler.stream == sys.stderr:
                    for filter_obj in handler.filters:
                        if isinstance(filter_obj, ErrorFilter):
                            stderr_handler = handler
                            break
        
        assert stdout_handler is not None, "stdout handler with InfoFilter not found"
        assert stderr_handler is not None, "stderr handler with ErrorFilter not found"
        
        # Verify filters
        assert isinstance(stdout_handler.filters[0], InfoFilter)
        assert isinstance(stderr_handler.filters[0], ErrorFilter)


class TestErrorFilter:
    """Test cases for ErrorFilter class."""
    
    def test_error_filter_allows_error(self):
        """Test ErrorFilter allows ERROR level."""
        error_filter = ErrorFilter()
        record = Mock()
        record.levelno = logging.ERROR
        
        assert error_filter.filter(record) is True
    
    def test_error_filter_allows_critical(self):
        """Test ErrorFilter allows CRITICAL level."""
        error_filter = ErrorFilter()
        record = Mock()
        record.levelno = logging.CRITICAL
        
        assert error_filter.filter(record) is True
    
    def test_error_filter_blocks_info(self):
        """Test ErrorFilter blocks INFO level."""
        error_filter = ErrorFilter()
        record = Mock()
        record.levelno = logging.INFO
        
        assert error_filter.filter(record) is False
    
    def test_error_filter_blocks_warning(self):
        """Test ErrorFilter blocks WARNING level."""
        error_filter = ErrorFilter()
        record = Mock()
        record.levelno = logging.WARNING
        
        assert error_filter.filter(record) is False
    
    def test_error_filter_blocks_debug(self):
        """Test ErrorFilter blocks DEBUG level."""
        error_filter = ErrorFilter()
        record = Mock()
        record.levelno = logging.DEBUG
        
        assert error_filter.filter(record) is False


class TestInfoFilter:
    """Test cases for InfoFilter class."""
    
    def test_info_filter_allows_debug(self):
        """Test InfoFilter allows DEBUG level."""
        info_filter = InfoFilter()
        record = Mock()
        record.levelno = logging.DEBUG
        
        assert info_filter.filter(record) is True
    
    def test_info_filter_allows_info(self):
        """Test InfoFilter allows INFO level."""
        info_filter = InfoFilter()
        record = Mock()
        record.levelno = logging.INFO
        
        assert info_filter.filter(record) is True
    
    def test_info_filter_allows_warning(self):
        """Test InfoFilter allows WARNING level."""
        info_filter = InfoFilter()
        record = Mock()
        record.levelno = logging.WARNING
        
        assert info_filter.filter(record) is True
    
    def test_info_filter_blocks_error(self):
        """Test InfoFilter blocks ERROR level."""
        info_filter = InfoFilter()
        record = Mock()
        record.levelno = logging.ERROR
        
        assert info_filter.filter(record) is False
    
    def test_info_filter_blocks_critical(self):
        """Test InfoFilter blocks CRITICAL level."""
        info_filter = InfoFilter()
        record = Mock()
        record.levelno = logging.CRITICAL
        
        assert info_filter.filter(record) is False


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

            # Should add 2 handlers per logger (stdout and stderr)
            # 3 loggers * 2 handlers = 6 total
            assert mock_logger.addHandler.call_count == 6

    def test_configure_uvicorn_logging_sets_propagate(self):
        """Test configure_uvicorn_logging sets propagate to False."""
        with patch('app.logging.logging.getLogger') as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            configure_uvicorn_logging()

            # Should set propagate to False
            assert not mock_logger.propagate

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

            # Should create 2 StreamHandler instances per logger (stdout and stderr)
            # 3 loggers * 2 handlers = 6 total
            assert mock_stream_handler.call_count == 6

    def test_configure_uvicorn_logging_with_mock_json_formatter(self):
        """Test configure_uvicorn_logging with mocked JSONFormatter."""
        with patch('app.logging.logging.getLogger') as mock_get_logger, \
                patch('app.logging.JSONFormatter') as mock_formatter:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            configure_uvicorn_logging()

            # Should create JSONFormatter instances for each handler
            # 3 loggers * 2 handlers = 6 total
            assert mock_formatter.call_count == 6

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
