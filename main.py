import asyncio
import signal
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.config.config import get_config, reload_config
from app.config.environment import get_environment_config
from app.config.validation import MessengerType
from app.file_lock import FileLock
from app.im.channel_manager import ChannelManager
from app.im.helpers import get_application
from app.im.user_store import UserUpdateScheduler
from app.incident.incidents import Incidents
from app.inhibition.manager import InhibitionManager
from app.jinja_template import JinjaTemplate
from app.logging import logger, configure_uvicorn_logging, configure_aiohttp_logging, configure_warnings_logging
from app.metrics import STATUS
from app.middleware import StandbyMiddleware
from app.queue.manager import AsyncQueueManager
from app.queue.queue import AsyncQueue
from app.route import generate_route
from app.cli import parse_arguments
from app.routes import create_router
from app.webhook import generate_webhooks


def setup_sighup_handler(fastapi_app=None):
    """Setup only SIGHUP signal handler for configuration reloading, preserving other Uvicorn handlers
    
    Args:
        fastapi_app: Optional FastAPI app instance for reloading component configurations
    """

    def handle_sighup(signum, frame):
        """Handle SIGHUP signal to reload configuration"""
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


def validate_config_only():
    try:
        get_config()
        logger.info("Configuration valid")
    except Exception as e:
        logger.error("Configuration validation failed", extra={'error': str(e)})
        sys.exit(1)


async def initialize_primary_server(fastapi_app: FastAPI, file_lock: FileLock) -> bool:
    """Initialize primary server components.
    
    Returns:
        True if initialization was successful, False otherwise.
    """
    if not file_lock.acquire_lock():
        logger.error("Failed to acquire lock")
        return False
    
    logger.info("Starting as primary server")
    
    try:
        config_data = get_config()
        route_config = config_data.app.route
        webhooks_config = config_data.app.webhooks

        route = generate_route(route_config)

        channel_manager = ChannelManager()
        if (config_data.messenger.type == MessengerType.NONE and
                (not config_data.messenger.channels or 'default' not in config_data.messenger.channels)):
            config_data.messenger.channels = {'default': {'id': 'default'}}
        channels = channel_manager.initialize(route.get_uniq_channels(), config_data.messenger.channels, route.channel)
        default_channel = route.channel

        messenger = get_application(config_data.messenger, channels, default_channel, 
                                    task_management_config=config_data.app.task_management)
        await messenger.initialize_async()
        
        webhooks = generate_webhooks(webhooks_config)
        incidents = Incidents.create_or_load(messenger.type, messenger.public_url, messenger.team)
        JinjaTemplate.set_incidents(incidents)

        queue = await AsyncQueue.recreate_queue(incidents)
        
        inhibition_manager = InhibitionManager(
            rules=config_data.app.inhibit_rules or [],
            incidents=incidents,
            application=messenger,
            queue=queue
        )
        inhibition_manager.restore_from_incidents()

        user_scheduler = UserUpdateScheduler(queue, messenger.type.value)
        messenger.configure_scheduler(user_scheduler)
        await user_scheduler.schedule_all_stored()
        queue_manager = AsyncQueueManager(queue, messenger, incidents, webhooks, route, inhibition_manager)

        fastapi_app.state.queue = queue
        fastapi_app.state.queue_manager = queue_manager
        fastapi_app.state.incidents = incidents
        fastapi_app.state.messenger = messenger
        fastapi_app.state.webhooks = webhooks
        fastapi_app.state.route = route
        fastapi_app.state.channel_manager = channel_manager
        fastapi_app.state.config = config_data
        fastapi_app.state.inhibition_manager = inhibition_manager

        queue_manager.start_processing()
        fastapi_app.state.is_standby = False
        STATUS.set(1)
        logger.info('Started as primary server')
        return True
    except Exception as e:
        logger.error("Primary server initialization failed", extra={'error': str(e)})
        await file_lock.release_lock()
        return False


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """Manage application lifecycle"""
    file_lock = FileLock()
    shutdown_event = asyncio.Event()

    can_take_over = file_lock.can_take_over_lock()
    is_standby = file_lock.is_locked() and not can_take_over

    fastapi_app.state.file_lock = file_lock
    fastapi_app.state.is_standby = is_standby
    fastapi_app.state.queue_manager = None
    fastapi_app.state.queue = AsyncQueue()
    fastapi_app.state.inhibition_manager = None
    
    async def wait_and_become_primary():
        """Background task to wait for lock and become primary server."""
        while not shutdown_event.is_set():
            await file_lock.wait_for_unlock()
            if shutdown_event.is_set():
                break
            logger.info('Transitioning to primary server')
            if await initialize_primary_server(fastapi_app, file_lock):
                break
            logger.error('Transition failed, retrying')
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=5.0)
                break
            except asyncio.TimeoutError:
                pass
    
    if is_standby:
        logger.info("Another IMPulse instance is running, working as standby server")
        hostname, pid = file_lock.get_lock_info()
        STATUS.set(0)
        logger.debug("Lock held by another instance", extra={'hostname': hostname, 'pid': pid})
        logger.info('IMPulse started in standby mode')
        unlock_task = asyncio.create_task(wait_and_become_primary())
    else:
        if can_take_over:
            hostname, pid = file_lock.get_lock_info()
            logger.debug("Taking over from dead process", extra={'hostname': hostname, 'pid': pid})
        success = await initialize_primary_server(fastapi_app, file_lock)
        if not success:
            logger.error('Primary server start failed, entering standby mode')
            fastapi_app.state.is_standby = True
            unlock_task = asyncio.create_task(wait_and_become_primary())
        else:
            unlock_task = None

    yield
    
    # Signal shutdown to background task
    shutdown_event.set()
    
    # Cancel and await background task
    if unlock_task:
        unlock_task.cancel()
        try:
            await unlock_task
        except asyncio.CancelledError:
            pass
        if fastapi_app.state.is_standby:
            logger.info('Shutting down standby server')
            return

    # Cleanup primary server resources
    if fastapi_app.state.queue_manager:
        await fastapi_app.state.queue_manager.stop_processing()
    if hasattr(fastapi_app.state, 'messenger') and hasattr(fastapi_app.state.messenger, 'close'):
        await fastapi_app.state.messenger.close()
    
    if hasattr(fastapi_app.state, 'messenger') and getattr(fastapi_app.state.messenger, 'task_management_integration', None):
        await fastapi_app.state.messenger.task_management_integration.jira_client.close()

    if hasattr(fastapi_app.state, 'messenger') and hasattr(fastapi_app.state.messenger, 'chains'):
        for chain in fastapi_app.state.messenger.chains.values():
            if hasattr(chain, 'cleanup'):
                chain.cleanup()
    
    await file_lock.release_lock()

    logger.info('Shutdown complete')


app = FastAPI(
    title="IMPulse",
    description="Incident Management Platform",
    version="0.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None
)
app.add_middleware(StandbyMiddleware)
config = get_config()
env_config = get_environment_config()
http_prefix = env_config.http_prefix

templates = None
if get_config().ui_config:
    app.mount(f"{http_prefix}/static", StaticFiles(directory="static"), name="static")
    templates = Jinja2Templates(directory="templates")

router = create_router(http_prefix, templates)
app.include_router(router)


if __name__ == "__main__":
    args = parse_arguments()

    if args.check:
        validate_config_only()
    else:
        setup_sighup_handler(app)

        import uvicorn

        configure_uvicorn_logging()
        configure_aiohttp_logging()
        configure_warnings_logging()

        config = get_config()
        env_config = get_environment_config()
        
        uvicorn.run(
            "main:app",
            host=env_config.listen_host,
            port=env_config.listen_port,
            reload=True,
            log_level="warning"
        )
