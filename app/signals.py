import os
import signal

from app.config.config import reload_config
from app.logging import logger


def setup_sighup_handler():
    def handle_sighup(signum, frame):
        try:
            logger.info("Reloading configuration")
            success = reload_config()
            if success:
                logger.info("Configuration reloaded")

                # if fastapi_app:
                #     config_data = get_config()
                #     if fastapi_app.state.inhibition_manager:
                #         fastapi_app.state.inhibition_manager.reload_rules(config_data.app.inhibit_rules or [])
        except Exception as e:
            logger.error("Configuration reload error", extra={'error': str(e)})
            logger.warning("Configuration reload aborted")

    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, handle_sighup)
        logger.debug("SIGHUP handler registered")
    else:
        logger.warning("SIGHUP signal not available on this platform")


def setup_sighup_forwarder():
    _handling = False

    def forward_sighup(signum, frame):
        nonlocal _handling
        if _handling:
            return
        _handling = True
        try:
            os.killpg(os.getpgid(os.getpid()), signal.SIGHUP)
        finally:
            _handling = False

    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, forward_sighup)
        logger.debug("SIGHUP forwarder registered")
