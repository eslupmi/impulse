import logging
import os
import sys


class CustomFormatter(logging.Formatter):
    fmt = '{asctime:<27}{levelname:<11}{message}'

    def __init__(self):
        super().__init__(self.fmt, style='{')


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
        stdout_handler.setFormatter(CustomFormatter())
        stdout_handler.addFilter(InfoFilter())
        logger.addHandler(stdout_handler)
    
    # Add stderr handler only if it doesn't exist
    if not has_stderr_handler:
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setFormatter(CustomFormatter())
        stderr_handler.addFilter(ErrorFilter())
        logger.addHandler(stderr_handler)
    
    return logger


def configure_uvicorn_logging():
    """Configure uvicorn and FastAPI loggers to use our custom formatter and appropriate levels"""
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.setLevel(logging.WARNING)

    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.setLevel(logging.WARNING)

    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
        logger_obj = logging.getLogger(logger_name)
        logger_obj.handlers.clear()
        
        # Handler for stdout (DEBUG, INFO, WARNING)
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(CustomFormatter())
        stdout_handler.addFilter(InfoFilter())
        logger_obj.addHandler(stdout_handler)
        
        # Handler for stderr (ERROR, CRITICAL)
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setFormatter(CustomFormatter())
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
