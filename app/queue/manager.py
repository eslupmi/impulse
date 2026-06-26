import asyncio

from app.logging import logger
from app.queue.constants import QueueItemType
from app.queue.handlers.alert_handler import AlertHandler
from app.queue.handlers.message_update_handler import MessageUpdateHandler
from app.queue.handlers.status_check_handler import StatusCheckHandler
from app.queue.handlers.status_update_handler import StatusUpdateHandler
from app.queue.handlers.step_handler import StepHandler
from app.queue.handlers.unfreeze_handler import UnfreezeHandler
from app.queue.handlers.user_update_handler import UserUpdateHandler


class AsyncQueueManager:
    """
    AsyncQueueManager class is responsible for handling the queue items asynchronously.
    """
    
    def __init__(self, queue, application, incidents, webhooks, route_, inhibition_manager, maintenance_manager):
        self.queue = queue
        self.application = application
        self.incidents = incidents
        self.inhibition_manager = inhibition_manager
        self.maintenance_manager = maintenance_manager
        self.step_handler = StepHandler(self.queue, application, incidents, webhooks)
        self.status_update_handler = StatusUpdateHandler(self.queue, application, incidents, inhibition_manager)
        self.status_check_handler = StatusCheckHandler(self.queue, application, incidents, inhibition_manager)
        self.message_update_handler = MessageUpdateHandler(self.queue, application, incidents)
        self.alert_handler = AlertHandler(self.queue, application, incidents, route_, inhibition_manager, maintenance_manager)
        self.unfreeze_handler = UnfreezeHandler(self.queue, application, incidents, maintenance_manager)
        self.user_update_handler = UserUpdateHandler(self.queue, application, incidents)
        self._running = False
        self._task = None

    async def handle_alert(self, alert_state: dict):
        await self.alert_handler.handle(alert_state)

    async def handle_message_update(self, uniq_id: str):
        await self.message_update_handler.handle(uniq_id)

    async def handle_status_check(self, uniq_id: str):
        await self.status_check_handler.handle(uniq_id)

    async def handle_status_update(self, uniq_id: str):
        await self.status_update_handler.handle(uniq_id)

    async def handle_step(self, uniq_id: str, identifier: str):
        await self.step_handler.handle(uniq_id, identifier)

    async def handle_unfreeze(self, uniq_id: str, data: str):
        await self.unfreeze_handler.handle(uniq_id, data)

    async def handle_maintenance_start(self, window_id: str):
        await self.maintenance_manager.handle_window_start(window_id)

    async def handle_maintenance_end(self, window_id: str):
        await self.maintenance_manager.handle_window_end(window_id)

    async def handle_user_update(self, user_id: str):
        await self.user_update_handler.handle(user_id)

    async def queue_handle_once(self):
        type_, uniq_id, identifier, data = await self.queue.get_next_ready_item()
        if type_ is None:
            return

        try:
            if type_ == QueueItemType.UPDATE_STATUS:
                await self.handle_status_update(uniq_id)
            elif type_ == QueueItemType.STATUS_CHECK:
                await self.handle_status_check(uniq_id)
            elif type_ == QueueItemType.UPDATE_MESSAGE:
                await self.handle_message_update(uniq_id)
            elif type_ == QueueItemType.CHAIN_STEP:
                await self.handle_step(uniq_id, identifier)
            elif type_ == QueueItemType.ALERT:
                await self.handle_alert(data)
            elif type_ == QueueItemType.UNFREEZE:
                await self.handle_unfreeze(uniq_id, data)
            elif type_ == QueueItemType.MAINTENANCE_START:
                await self.handle_maintenance_start(identifier)
            elif type_ == QueueItemType.MAINTENANCE_END:
                await self.handle_maintenance_end(identifier)
            elif type_ == QueueItemType.UPDATE_USER:
                await self.handle_user_update(identifier)
        except Exception as e:
            logger.error(f"Error handling queue item {type_}", extra={'error': repr(e)})
        
        # Always yield control after processing an item
        await asyncio.sleep(0)

    def start_processing(self):
        if self._running:
            return
            
        self._running = True
        self._task = asyncio.create_task(self._process_queue_loop())
        logger.info("Started Queue")

    async def stop_processing(self):
        if not self._running:
            return

        self._running = False
        if self._task is not None:
            await self._task
            self._task = None
        logger.info("Stopped queue")

    async def _process_queue_loop(self):
        while self._running:
            try:
                await self.queue_handle_once()
            except Exception as e:
                logger.error(f"Error in queue processing loop: {e}")
                if self._running:
                    await asyncio.sleep(1)
                continue
            if not self._running:
                break
            await asyncio.sleep(0.1)
