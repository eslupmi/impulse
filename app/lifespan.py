import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config.config import get_config
from app.config.validation import MessengerType
from app.file_lock import FileLock
from app.im.chain.ui_chains_store import ui_chains_store
from app.im.channel_manager import ChannelManager
from app.im.helpers import get_application
from app.im.user_store import UserUpdateScheduler
from app.incident.incidents import Incidents
from app.inhibition.manager import InhibitionManager
from app.jinja_template import JinjaTemplate
from app.logging import logger
from app.maintenance.manager import MaintenanceManager
from app.maintenance.store import get_maintenance_store
from app.metrics import STATUS
from app.queue.manager import AsyncQueueManager
from app.queue.queue import AsyncQueue
from app.route import generate_route
from app.signals import setup_sighup_handler
from app.s3_lock import S3Lock
from app.storage import S3Storage, get_storage
from app.ui.websocket import incident_ws
from app.webhook import generate_webhooks


async def _initialize_primary_server(fastapi_app: FastAPI, file_lock: FileLock | S3Lock) -> bool:
    if isinstance(file_lock, S3Lock):
        acquisition = asyncio.create_task(asyncio.to_thread(file_lock.acquire_lock))
        try:
            acquired = await asyncio.shield(acquisition)
        except asyncio.CancelledError:
            await acquisition
            await file_lock.release_lock()
            raise
    else:
        acquired = file_lock.acquire_lock()
    if not acquired:
        logger.error("Failed to acquire lock")
        return False

    logger.info("Starting as primary server")

    initialization = asyncio.create_task(create_main_objects(fastapi_app))
    ownership_lost = asyncio.create_task(_wait_for_ownership_loss(file_lock))
    try:
        try:
            await asyncio.wait({initialization, ownership_lost}, return_when=asyncio.FIRST_COMPLETED)
            _require_ownership(file_lock)
            await initialization
        finally:
            initialization.cancel()
            ownership_lost.cancel()
            await asyncio.gather(initialization, ownership_lost, return_exceptions=True)
        fastapi_app.state.is_standby = False
        STATUS.set(1)
        logger.info('Started as primary server')
        return True
    except (Exception, asyncio.CancelledError) as error:
        if not isinstance(error, asyncio.CancelledError):
            logger.error("Primary server initialization failed")
        fastapi_app.state.is_standby = True
        STATUS.set(0)
        try:
            await _cleanup_application_objects(fastapi_app, cancel=True)
        finally:
            await file_lock.release_lock()
        if isinstance(error, asyncio.CancelledError):
            raise
        return False


def _require_ownership(file_lock):
    if file_lock is not None and not file_lock.check_owned():
        raise OSError('Storage lock is not owned by this instance')


async def create_main_objects(fastapi_app: FastAPI, reload=False):
    file_lock = getattr(fastapi_app.state, 'file_lock', None)
    _require_ownership(file_lock)
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
        config_data.messenger, channels, default_channel,
        task_management_config=config_data.app.task_management,
        webhooks=webhooks_config,
    )
    previous_messenger = getattr(fastapi_app.state, 'messenger', None)
    fastapi_app.state.messenger = messenger
    await messenger.initialize_async()
    _require_ownership(file_lock)
    webhooks = generate_webhooks(webhooks_config)
    messenger.webhooks = webhooks

    if reload:
        if previous_messenger is None:
            raise RuntimeError('Cannot reload an uninitialized primary')
        user_scheduler = previous_messenger._user_scheduler
        fastapi_app.state.inhibition_manager.reload_rules(config_data.app.inhibit_rules)
        await fastapi_app.state.inhibition_manager.reconcile_orphans()
        _require_ownership(file_lock)
        messenger.configure_scheduler(user_scheduler)
        fastapi_app.state.queue_manager.reload_runtime(messenger, webhooks, route)
    else:
        incidents = Incidents.create_or_load(messenger.type, messenger.public_url, messenger.team)
        JinjaTemplate.set_incidents(incidents)
        queue = await AsyncQueue.recreate_queue(incidents)
        _require_ownership(file_lock)
        inhibition_manager = InhibitionManager(
            rules=config_data.app.inhibit_rules,
            incidents=incidents,
            application=messenger,
            queue=queue
        )
        inhibition_manager.restore_from_incidents()
        maintenance_manager = MaintenanceManager(
            store=get_maintenance_store(),
            incidents=incidents,
            application=messenger,
            queue=queue,
        )
        inhibition_manager.attach_maintenance_manager(maintenance_manager)
        await inhibition_manager.reconcile_orphans()
        _require_ownership(file_lock)
        user_scheduler = UserUpdateScheduler(queue, messenger.type.value)
        messenger.configure_scheduler(user_scheduler)
        await user_scheduler.schedule_all_stored()
        _require_ownership(file_lock)
        queue_manager = AsyncQueueManager(queue, messenger, incidents, webhooks, route, inhibition_manager, maintenance_manager)
        queue_manager.check_owned = file_lock.check_owned if file_lock is not None else None
        fastapi_app.state.queue_manager = queue_manager
        await maintenance_manager.reconcile_all()
        _require_ownership(file_lock)
        await maintenance_manager.schedule_window_starts()
        _require_ownership(file_lock)
        await maintenance_manager.broadcast_active_maintenance()
        _require_ownership(file_lock)
        ui_chains_store.prune_all()
        get_maintenance_store().prune_expired_windows()

        fastapi_app.state.incidents = incidents
        fastapi_app.state.queue = queue
        fastapi_app.state.inhibition_manager = inhibition_manager
        fastapi_app.state.maintenance_manager = maintenance_manager

    fastapi_app.state.messenger = messenger
    fastapi_app.state.webhooks = webhooks
    fastapi_app.state.route = route
    fastapi_app.state.channel_manager = channel_manager

    _require_ownership(file_lock)
    if not reload:
        queue_manager.start_processing()


async def _cleanup_application_objects(fastapi_app: FastAPI, reload=False, cancel=False):
    queue_manager = getattr(fastapi_app.state, 'queue_manager', None)
    if queue_manager and not reload:
        await queue_manager.stop_processing(cancel=cancel)
    messenger = getattr(fastapi_app.state, 'messenger', None)
    if cancel:
        tasks = set(getattr(fastapi_app.state, 'runtime_tasks', ()))
        if messenger is not None:
            tasks.update(messenger._async_tasks)
            if messenger._user_scheduler is not None:
                tasks.update(messenger._user_scheduler._async_tasks)
        tasks.discard(asyncio.current_task())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        sockets = list(incident_ws.connections)
        await asyncio.gather(*(socket.close(code=1012) for socket in sockets), return_exceptions=True)
        for socket in sockets:
            incident_ws.disconnect(socket)
    if messenger is not None:
        await messenger.close()
        if messenger.task_management_integration is not None:
            await messenger.task_management_integration.jira_client.close()
        for chain in messenger.chains.values():
            if hasattr(chain, 'cleanup'):
                chain.cleanup()
    if not reload:
        fastapi_app.state.queue_manager = None
        fastapi_app.state.messenger = None


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    setup_sighup_handler(fastapi_app, create_main_objects, _cleanup_application_objects)

    storage = get_storage()
    file_lock = S3Lock(storage) if isinstance(storage, S3Storage) else FileLock()
    if isinstance(storage, S3Storage):
        storage.check_owned = file_lock.check_owned
    shutdown_event = asyncio.Event()

    can_take_over = file_lock.can_take_over_lock()
    is_standby = file_lock.is_locked() and not can_take_over

    fastapi_app.state.file_lock = file_lock
    fastapi_app.state.is_standby = True
    fastapi_app.state.runtime_tasks = set()
    fastapi_app.state.queue_manager = None
    fastapi_app.state.messenger = None
    fastapi_app.state.queue = AsyncQueue()
    fastapi_app.state.inhibition_manager = None
    fastapi_app.state.maintenance_manager = None

    if is_standby:
        logger.info("Another IMPulse instance is running, working as standby server")
        hostname, pid = file_lock.get_lock_info()
        STATUS.set(0)
        logger.debug("Lock held by another instance", extra={'hostname': hostname, 'pid': pid})
        logger.info('IMPulse started in standby mode')
    else:
        if can_take_over:
            hostname, pid = file_lock.get_lock_info()
            logger.debug("Taking over from dead process", extra={'hostname': hostname, 'pid': pid})
        success = await _initialize_primary_server(fastapi_app, file_lock)
        if not success:
            logger.error('Primary server start failed, entering standby mode')
    ownership_task = asyncio.create_task(_maintain_primary(shutdown_event, file_lock, fastapi_app))

    try:
        yield
    finally:
        shutdown_event.set()
        ownership_task.cancel()
        try:
            await ownership_task
        except asyncio.CancelledError:
            pass
        was_primary = fastapi_app.state.queue_manager is not None or fastapi_app.state.messenger is not None
        fastapi_app.state.is_standby = True
        STATUS.set(0)
        if was_primary:
            try:
                await _cleanup_application_objects(fastapi_app)
            finally:
                await file_lock.release_lock()
            logger.info('Shutdown complete')
        else:
            logger.info('Shutting down standby server')


async def _maintain_primary(shutdown_event, file_lock, fastapi_app):
    while not shutdown_event.is_set():
        if fastapi_app.state.is_standby:
            await file_lock.wait_for_unlock()
            if shutdown_event.is_set():
                break
            logger.info('Transitioning to primary server')
            if not await _initialize_primary_server(fastapi_app, file_lock):
                logger.error('Transition failed, retrying')
                try:
                    await asyncio.wait_for(shutdown_event.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    pass
            continue
        await _wait_for_ownership_loss(file_lock)
        fastapi_app.state.is_standby = True
        STATUS.set(0)
        logger.error('Storage lock lost, entering standby mode')
        try:
            await _cleanup_application_objects(fastapi_app, cancel=True)
        finally:
            await file_lock.release_lock()


async def _wait_for_ownership_loss(file_lock):
    while await asyncio.to_thread(file_lock.check_owned):
        await asyncio.sleep(0.25)
