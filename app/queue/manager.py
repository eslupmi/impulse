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
    
    def __init__(self, queue, application, incidents, webhooks, route_, inhibition_manager):
        """
        Initialize AsyncQueueManager object.

        :param queue: AsyncQueue object.
        :param application: Application object.
        :param incidents: Incidents object.
        :param webhooks: Webhooks object.
        :param route_: Route object
        :param inhibition_manager: InhibitionManager object for inhibition rule handling
        """
        self.queue = queue
        self.application = application
        self.incidents = incidents
        self.inhibition_manager = inhibition_manager
        self.step_handler = StepHandler(self.queue, application, incidents, webhooks)
        self.status_update_handler = StatusUpdateHandler(self.queue, application, incidents, inhibition_manager)
        self.status_check_handler = StatusCheckHandler(self.queue, application, incidents, inhibition_manager)
        self.message_update_handler = MessageUpdateHandler(self.queue, application, incidents)
        self.alert_handler = AlertHandler(self.queue, application, incidents, route_, inhibition_manager)
        self.unfreeze_handler = UnfreezeHandler(self.queue, application, incidents)
        self.user_update_handler = UserUpdateHandler(self.queue, application, incidents)
        self._running = False
        self._task = None

    async def handle_step(self, uniq_id: str, identifier: str):
        """
        Handle step.

        :param uniq_id: String unique id.
        :param identifier: String identifier.
        """
        await self.step_handler.handle(uniq_id, identifier)

    async def handle_status_update(self, uniq_id: str):
        """
        Handle status update.
        :param uniq_id: String unique id.
        """
        await self.status_update_handler.handle(uniq_id)

    async def handle_status_check(self, uniq_id: str):
        """
        Check incident status and perform appropriate actions (deletion, file removal, etc.)
        :param uniq_id: String unique id.
        """
        await self.status_check_handler.handle(uniq_id)

    async def handle_message_update(self, uniq_id: str):
        """
        Handle message update without status changes.
        :param uniq_id: String unique id.
        """
        await self.message_update_handler.handle(uniq_id)

    async def handle_alert(self, alert_state: dict):
        """
        Handle alert.
        :param alert_state: Dictionary alert_state.
        """
        await self.alert_handler.handle(alert_state)

    async def handle_unfreeze(self, uniq_id: str):
        """
        Handle unfreeze.
        :param uniq_id: String unique id.
        """
        await self.unfreeze_handler.handle(uniq_id)

    async def handle_user_update(self, user_id: str):
        """
        Handle user data refresh.
        :param user_id: User ID to refresh.
        """
        await self.user_update_handler.handle(user_id)

    async def queue_handle_once(self):
        """
        Handle one queue item.
        The method handles the next ready queue item. Calls the appropriate handler based on the type of the item.
        """
        # Don't check items count - just try to get next item
        # The get_next_ready_item() method handles empty queue safely
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
                await self.handle_unfreeze(uniq_id)
            elif type_ == QueueItemType.UPDATE_USER:
                await self.handle_user_update(identifier)
        except Exception as e:
            logger.error(f"Error handling queue item {type_}: {repr(e)}")
        
        # Always yield control after processing an item
        await asyncio.sleep(0)

    def start_processing(self):
        """Start the background queue processing task"""
        if self._running:
            return
            
        self._running = True
        self._task = asyncio.create_task(self._process_queue_loop())
        logger.info("Started Queue")

    async def stop_processing(self):
        """Stop the background queue processing task"""
        if not self._running:
            return
            
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                # Expected when cancelling the task, suppress the exception
                pass
        logger.info("Stopped queue")

    async def _process_queue_loop(self):
        """Main queue processing loop"""
        while self._running:
            try:
                await self.queue_handle_once()
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in queue processing loop: {e}")
                await asyncio.sleep(1)
