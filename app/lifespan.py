import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.config.config import get_config
from app.config.environment import get_environment_config
from app.config.validation import MessengerType
from app.signals import setup_sighup_handler
from app.file_lock import FileLock
from app.routes import create_router
from app.im.channel_manager import ChannelManager
from app.im.helpers import get_application
from app.im.user_store import UserUpdateScheduler
from app.incident.incidents import Incidents
from app.inhibition.manager import InhibitionManager
from app.jinja_template import JinjaTemplate
from app.logging import logger
from app.metrics import STATUS
from app.queue.manager import AsyncQueueManager
from app.queue.queue import AsyncQueue
from app.route import generate_route
from app.webhook import generate_webhooks


async def _initialize_primary_server(fastapi_app: FastAPI, file_lock: FileLock) -> bool:
    if not file_lock.acquire_lock():
        logger.error("Failed to acquire lock")
        return False

    logger.info("Starting as primary server")

    try:
        await create_main_objects(fastapi_app)
        STATUS.set(1)
        logger.info('Started as primary server')
        return True
    except Exception as e:
        logger.error("Primary server initialization failed", extra={'error': str(e)})
        await file_lock.release_lock()
        return False


async def create_main_objects(fastapi_app: FastAPI, reload=False):
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
    messenger = get_application(
        config_data.messenger, channels, default_channel, task_management_config=config_data.app.task_management
    )
    await messenger.initialize_async()
    webhooks = generate_webhooks(webhooks_config)

    if reload:
        fastapi_app.state.inhibition_manager.reload_rules(config_data.app.inhibit_rules)
    else:
        incidents = Incidents.create_or_load(messenger.type, messenger.public_url, messenger.team)
        JinjaTemplate.set_incidents(incidents)
        queue = await AsyncQueue.recreate_queue(incidents)
        inhibition_manager = InhibitionManager(
            rules=config_data.app.inhibit_rules,
            incidents=incidents,
            application=messenger,
            queue=queue
        )

        deleted_incidents = [
            incident for incident in incidents.uniq_ids.values()
            if incident.status == 'deleted' and not (incident.is_frozen() and incident.frozen_until is not None)
        ]
        for incident in deleted_incidents:
            await inhibition_manager.handle_closed(incident)
            incidents.del_by_uniq_id(incident.uniq_id)
            logger.info("Deleted incident", extra={'uuid': incident.uuid})

        inhibition_manager.restore_from_incidents()
        user_scheduler = UserUpdateScheduler(queue, messenger.type.value)
        messenger.configure_scheduler(user_scheduler)
        await user_scheduler.schedule_all_stored()
        queue_manager = AsyncQueueManager(queue, messenger, incidents, webhooks, route, inhibition_manager)

        fastapi_app.state.queue_manager = queue_manager
        fastapi_app.state.incidents = incidents
        fastapi_app.state.queue = queue
        fastapi_app.state.inhibition_manager = inhibition_manager

    fastapi_app.state.messenger = messenger
    fastapi_app.state.webhooks = webhooks
    fastapi_app.state.route = route
    fastapi_app.state.channel_manager = channel_manager

    if not reload:
        queue_manager.start_processing()
    fastapi_app.state.is_standby = False


async def _cleanup_application_objects(fastapi_app: FastAPI, reload = False):
    if fastapi_app.state.queue_manager and not reload:
        await fastapi_app.state.queue_manager.stop_processing()
    if hasattr(fastapi_app.state, 'messenger') and hasattr(fastapi_app.state.messenger, 'close'):
        await fastapi_app.state.messenger.close()

    if hasattr(fastapi_app.state, 'messenger') and getattr(fastapi_app.state.messenger, 'task_management_integration', None):
        await fastapi_app.state.messenger.task_management_integration.jira_client.close()

    if hasattr(fastapi_app.state, 'messenger') and hasattr(fastapi_app.state.messenger, 'chains'):
        for chain in fastapi_app.state.messenger.chains.values():
            if hasattr(chain, 'cleanup'):
                chain.cleanup()


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    setup_sighup_handler(fastapi_app, create_main_objects, _cleanup_application_objects)

    env_config = get_environment_config()
    http_prefix = env_config.http_prefix
    router = create_router(http_prefix, fastapi_app)
    fastapi_app.include_router(router)

    file_lock = FileLock()
    shutdown_event = asyncio.Event()

    can_take_over = file_lock.can_take_over_lock()
    is_standby = file_lock.is_locked() and not can_take_over

    fastapi_app.state.file_lock = file_lock
    fastapi_app.state.is_standby = is_standby
    fastapi_app.state.queue_manager = None
    fastapi_app.state.queue = AsyncQueue()
    fastapi_app.state.inhibition_manager = None

    if is_standby:
        logger.info("Another IMPulse instance is running, working as standby server")
        hostname, pid = file_lock.get_lock_info()
        STATUS.set(0)
        logger.debug("Lock held by another instance", extra={'hostname': hostname, 'pid': pid})
        logger.info('IMPulse started in standby mode')
        unlock_task = asyncio.create_task(_wait_and_become_primary(shutdown_event, file_lock, fastapi_app))
    else:
        if can_take_over:
            hostname, pid = file_lock.get_lock_info()
            logger.debug("Taking over from dead process", extra={'hostname': hostname, 'pid': pid})
        success = await _initialize_primary_server(fastapi_app, file_lock)
        if not success:
            logger.error('Primary server start failed, entering standby mode')
            fastapi_app.state.is_standby = True
            unlock_task = asyncio.create_task(_wait_and_become_primary(shutdown_event, file_lock, fastapi_app))
        else:
            unlock_task = None

    yield

    shutdown_event.set()

    if unlock_task:
        unlock_task.cancel()
        try:
            await unlock_task
        except asyncio.CancelledError:
            pass
        if fastapi_app.state.is_standby:
            logger.info('Shutting down standby server')
            return

    await _cleanup_application_objects(fastapi_app)

    await file_lock.release_lock()

    logger.info('Shutdown complete')


async def _wait_and_become_primary(shutdown_event, file_lock, fastapi_app):
    while not shutdown_event.is_set():
        await file_lock.wait_for_unlock()
        if shutdown_event.is_set():
            break
        logger.info('Transitioning to primary server')
        if await _initialize_primary_server(fastapi_app, file_lock):
            break
        logger.error('Transition failed, retrying')
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=5.0)
            break
        except asyncio.TimeoutError:
            pass
