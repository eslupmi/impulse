import logging
import os
import sys
import warnings
from datetime import datetime, timezone

from pythonjsonlogger import jsonlogger
from app.config.environment import get_environment_config

DEFAULT_JSON_FORMAT = '%(time)s %(level)s %(module)s %(message)s'

# Simple JSON formatter with custom timestamp and field filtering
class JSONFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        # Custom timestamp format
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        log_record['time'] = dt.strftime('%Y-%m-%dT%H:%M:%S') + f'.{int(record.msecs):03d}Z'
        log_record['level'] = record.levelname
        log_record['module'] = record.module
        # Remove unwanted fields
        for field in ['taskName', 'threadName', 'processName', 'process', 'thread', 
                      'relativeCreated', 'asctime', 'filename', 'funcName', 'lineno', 
                      'pathname', 'name', 'args', 'exc_info', 'exc_text', 'stack_info']:
            log_record.pop(field, None)

# Filters for stdout/stderr separation
class ErrorFilter(logging.Filter):
    def filter(self, record):
        return record.levelno >= logging.ERROR

class InfoFilter(logging.Filter):
    def filter(self, record):
        return record.levelno < logging.ERROR

def create_logger(name, level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    # Avoid duplicate handlers
    if not any(isinstance(h, logging.StreamHandler) and h.stream == sys.stdout 
               and any(isinstance(f, InfoFilter) for f in h.filters) 
               for h in logger.handlers):
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(JSONFormatter(DEFAULT_JSON_FORMAT))
        h.addFilter(InfoFilter())
        logger.addHandler(h)
    if not any(isinstance(h, logging.StreamHandler) and h.stream == sys.stderr 
               and any(isinstance(f, ErrorFilter) for f in h.filters) 
               for h in logger.handlers):
        h = logging.StreamHandler(sys.stderr)
        h.setFormatter(JSONFormatter(DEFAULT_JSON_FORMAT))
        h.addFilter(ErrorFilter())
        logger.addHandler(h)
    return logger

def configure_uvicorn_logging():
    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
        logger_obj = logging.getLogger(logger_name)
        logger_obj.setLevel(logging.WARNING)
        logger_obj.handlers.clear()
        for stream, filter_class in [(sys.stdout, InfoFilter), (sys.stderr, ErrorFilter)]:
            h = logging.StreamHandler(stream)
            h.setFormatter(JSONFormatter(DEFAULT_JSON_FORMAT))
            h.addFilter(filter_class())
            logger_obj.addHandler(h)
        logger_obj.propagate = False

def configure_aiohttp_logging():
    """Configure aiohttp logger to use JSON formatter"""
    aiohttp_logger = logging.getLogger('aiohttp')
    aiohttp_logger.setLevel(logging.WARNING)  # Only warnings and errors
    aiohttp_logger.handlers.clear()
    for stream, filter_class in [(sys.stdout, InfoFilter), (sys.stderr, ErrorFilter)]:
        h = logging.StreamHandler(stream)
        h.setFormatter(JSONFormatter(DEFAULT_JSON_FORMAT))
        h.addFilter(filter_class())
        aiohttp_logger.addHandler(h)
    aiohttp_logger.propagate = False

def configure_warnings_logging():
    """Redirect Python warnings to logging system"""
    def warning_to_log(message, category, filename, lineno, file=None, line=None):
        logger.warning(f"{category.__name__}: {message}", extra={'warning_category': category.__name__})
    
    warnings.showwarning = warning_to_log

# Initialize logger
try:
    log_level = getattr(logging, get_environment_config().log_level, logging.INFO)
except ImportError:
    log_level = getattr(logging, os.getenv('LOG_LEVEL', 'INFO').upper(), logging.INFO)

logger = create_logger('main_logger', log_level)
