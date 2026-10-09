import asyncio
import os
import signal

from fastapi import FastAPI

from app.config.config import reload_config
from app.logging import logger
from app.middleware import is_standby_mode


def setup_sighup_handler(fastapi_app: FastAPI, create_main_objects, cleanup_application_objects):
    def handle_sighup(signum, frame):
        try:
            logger.info("Reloading configuration")
            success = reload_config()
            if success and fastapi_app and not is_standby_mode(fastapi_app.state):
                async def reload():
                    if is_standby_mode(fastapi_app.state):
                        return
                    await cleanup_application_objects(fastapi_app, reload=True)
                    await create_main_objects(fastapi_app, reload=True)
                    logger.info("Configuration reloaded")
                try:
                    task = asyncio.get_running_loop().create_task(reload())
                    tasks = getattr(fastapi_app.state, 'runtime_tasks', None)
                    if tasks is not None:
                        tasks.add(task)
                        task.add_done_callback(tasks.discard)
                except RuntimeError:
                    asyncio.run(reload())
        except Exception as e:  # noqa: BLE001
            logger.error("Configuration reload error", extra={'error': str(e)})
            logger.warning("Configuration reload aborted")

    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, handle_sighup)
        logger.debug("SIGHUP handler registered")
    else:
        logger.warning("SIGHUP signal not available on this platform")


def setup_sighup_forwarder():
    def forward_sighup(signum, frame):
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
        try:
            pgid = os.getpgrp()
            os.killpg(pgid, signal.SIGHUP)
        finally:
            signal.signal(signal.SIGHUP, forward_sighup)

    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, forward_sighup)
