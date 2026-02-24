import signal

from app.config.config import get_config, reload_config
from app.logging import logger


def setup_sighup_handler(fastapi_app=None):
    def handle_sighup(signum, frame):
        try:
            logger.info("Reloading configuration")
            success = reload_config()
            if success:
                logger.info("Configuration reloaded")

                if fastapi_app and fastapi_app.state.inhibition_manager:
                    config_data = get_config()
                    fastapi_app.state.inhibition_manager.reload_rules(config_data.app.inhibit_rules or [])
        except Exception as e:
            logger.error("Configuration reload error", extra={'error': str(e)})
            logger.warning("Configuration reload aborted")

    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, handle_sighup)
        logger.debug("SIGHUP handler registered")
    else:
        logger.warning("SIGHUP signal not available on this platform")
