import asyncio
import os
import signal

from fastapi import FastAPI

from app.config.config import reload_config
from app.logging import logger


def setup_sighup_handler(fastapi_app: FastAPI, create_main_objects, cleanup_application_objects):
    def handle_sighup(signum, frame):
        try:
            logger.info("Reloading configuration")
            success = reload_config()
            if success:
                if fastapi_app:
                    async def reload():
                        await cleanup_application_objects(fastapi_app)
                        await create_main_objects(fastapi_app)
                    try:
                        asyncio.get_running_loop().create_task(reload())
                    except RuntimeError:
                        asyncio.run(reload())
                logger.info("Configuration reloaded")
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
