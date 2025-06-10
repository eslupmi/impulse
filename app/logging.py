import logging

from config import log_level


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


def create_logger(name, level=logging.INFO):
    lr = logging.getLogger(name)
    sh = logging.StreamHandler()
    lr.setLevel(level)
    sh.setFormatter(CustomFormatter())
    lr.addHandler(sh)
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
        handler = logging.StreamHandler()
        handler.setFormatter(CustomFormatter())
        logger_obj.addHandler(handler)
        logger_obj.propagate = False


log_level = getattr(logging, log_level.upper(), logging.INFO)
logger = create_logger('main_logger', log_level)
