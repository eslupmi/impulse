import logging
import os
import sys


class CustomFormatter(logging.Formatter):
    grey = "\033[2;97m"
    yellow = "\033[0;33m"
    white = "\033[0;97m"
    red = "\033[0;31m"
    bold_red = "\033[0;1m"
    reset = "\033[0;97m"
    format = '{asctime:<27}{levelname:<11}{message}'

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: white + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, style='{')
        return formatter.format(record)


class ErrorFilter(logging.Filter):
    """Filter to allow only ERROR and CRITICAL levels"""
    def filter(self, record):
        return record.levelno >= logging.ERROR


class InfoFilter(logging.Filter):
    """Filter to allow only DEBUG, INFO, and WARNING levels"""
    def filter(self, record):
        return record.levelno < logging.ERROR


def create_logger(name, level=logging.INFO):
    lr = logging.getLogger(name)
    lr.setLevel(level)
    
    # Handler for stdout (DEBUG, INFO, WARNING)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(CustomFormatter())
    stdout_handler.addFilter(InfoFilter())
    lr.addHandler(stdout_handler)
    
    # Handler for stderr (ERROR, CRITICAL)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(CustomFormatter())
    stderr_handler.addFilter(ErrorFilter())
    lr.addHandler(stderr_handler)
    
    return lr


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
    log_level = os.getenv('LOG_LEVEL', default='INFO')
    log_level = getattr(logging, log_level.upper(), logging.INFO)

logger = create_logger('main_logger', log_level)
