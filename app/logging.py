import logging
import os
import sys
from datetime import datetime, timezone
from pythonjsonlogger import jsonlogger


class JSONFormatter(jsonlogger.JsonFormatter):
    """Format log records as JSON using python-json-logger"""

    def __init__(self, *args, **kwargs):
        # Configure format string to include time, level, module, and message
        # python-json-logger will automatically add extra fields
        format_string = '%(time)s %(level)s %(module)s %(message)s'
        super().__init__(format_string, *args, **kwargs)

    def add_fields(self, log_record, record, message_dict):
        """Override to customize timestamp format and handle extra_fields"""
        super().add_fields(log_record, record, message_dict)
        
        # Format timestamp as ISO 8601 with milliseconds and Z suffix (UTC)
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        log_record['time'] = dt.strftime('%Y-%m-%dT%H:%M:%S') + f'.{int(record.msecs):03d}Z'
        
        # Ensure level is a string
        log_record['level'] = record.levelname
        
        # Ensure module is included
        log_record['module'] = record.module
        
        # Remove unwanted fields that python-json-logger adds automatically
        # (like taskName from asyncio tasks)
        unwanted_fields = ['taskName', 'threadName', 'processName', 'process', 'thread', 
                          'relativeCreated', 'asctime', 'filename', 'funcName', 'lineno', 
                          'pathname', 'name', 'args', 'exc_info', 'exc_text', 'stack_info']
        for field in unwanted_fields:
            log_record.pop(field, None)
        
        # # # Add extra_fields if present
        # # In Python logging, extra={'extra_fields': {...}} creates record.extra_fields attribute
        # if hasattr(record, 'extra_fields') and isinstance(record.extra_fields, dict):
        #     log_record.update(record.extra_fields)


class ErrorFilter(logging.Filter):
    """Filter to allow only ERROR and CRITICAL levels"""
    def filter(self, record):
        return record.levelno >= logging.ERROR


class InfoFilter(logging.Filter):
    """Filter to allow only DEBUG, INFO, and WARNING levels"""
    def filter(self, record):
        return record.levelno < logging.ERROR


def create_logger(name, level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Check if handlers already exist to avoid duplicates
    has_stdout_handler = False
    has_stderr_handler = False

    for handler in logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            if handler.stream == sys.stdout:
                # Check if it has InfoFilter
                for filter_obj in handler.filters:
                    if isinstance(filter_obj, InfoFilter):
                        has_stdout_handler = True
                        break
            elif handler.stream == sys.stderr:
                # Check if it has ErrorFilter
                for filter_obj in handler.filters:
                    if isinstance(filter_obj, ErrorFilter):
                        has_stderr_handler = True
                        break

    # Add stdout handler only if it doesn't exist
    if not has_stdout_handler:
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(JSONFormatter())
        stdout_handler.addFilter(InfoFilter())
        logger.addHandler(stdout_handler)

    # Add stderr handler only if it doesn't exist
    if not has_stderr_handler:
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setFormatter(JSONFormatter())
        stderr_handler.addFilter(ErrorFilter())
        logger.addHandler(stderr_handler)

    return logger


def configure_uvicorn_logging():
    """Configure uvicorn and FastAPI loggers to use JSON formatter and appropriate levels"""
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.setLevel(logging.WARNING)

    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.setLevel(logging.WARNING)

    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
        logger_obj = logging.getLogger(logger_name)
        logger_obj.handlers.clear()

        # Handler for stdout (DEBUG, INFO, WARNING)
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(JSONFormatter())
        stdout_handler.addFilter(InfoFilter())
        logger_obj.addHandler(stdout_handler)

        # Handler for stderr (ERROR, CRITICAL)
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setFormatter(JSONFormatter())
        stderr_handler.addFilter(ErrorFilter())
        logger_obj.addHandler(stderr_handler)

        logger_obj.propagate = False


try:
    from app.config.environment import get_environment_config
    env_config = get_environment_config()
    log_level = getattr(logging, env_config.log_level, logging.INFO)
except ImportError:
    # Fallback for cases where the config system isn't available yet
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    log_level = getattr(logging, log_level.upper(), logging.INFO)


logger = create_logger('main_logger', log_level)
