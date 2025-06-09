import asyncio
from app.queue.handlers.alert_handler import AlertHandler
from app.queue.handlers.status_update_handler import StatusUpdateHandler
from app.queue.handlers.step_handler import StepHandler
from app.queue.handlers.update_handler import UpdateHandler
from app.logging import logger


class AsyncQueueManager:
    """
    AsyncQueueManager class is responsible for handling the queue items asynchronously.
    """
    
    def __init__(self, queue, application, incidents, webhooks, route_):
        """
        Initialize AsyncQueueManager object.

        :param queue: AsyncQueue object.
        :param application: Application object.
        :param incidents: Incidents object.
        :param webhooks: Webhooks object.
        :param route_: Route object
        """
        self.queue = queue
        self.update_handler = UpdateHandler(self.queue, application, incidents)
        self.step_handler = StepHandler(self.queue, application, incidents, webhooks)
        self.status_update_handler = StatusUpdateHandler(self.queue, application, incidents)
        self.alert_handler = AlertHandler(self.queue, application, incidents, route_)
        self._running = False
        self._task = None

    async def handle_check_update(self, identifier: str):
        """
        Handle check update.
        :param identifier: String identifier.
        """
        await self.update_handler.handle(identifier)

    async def handle_step(self, uuid_: str, identifier: str):
        """
        Handle step.

        :param uuid_: String uuid.
        :param identifier: String identifier.
        """
        await self.step_handler.handle(uuid_, identifier)

    async def handle_status_update(self, uuid_: str):
        """
        Handle status update.
        :param uuid_: String uuid.
        """
        await self.status_update_handler.handle(uuid_)

    async def handle_alert(self, alert_state: dict):
        """
        Handle alert.
        :param alert_state: Dictionary alert_state.
        """
        await self.alert_handler.handle(alert_state)

    async def queue_handle_once(self):
        """
        Handle one queue item.
        The method handles the next ready queue item. Calls the appropriate handler based on the type of the item.
        """
        # Don't check items count - just try to get next item
        # The get_next_ready_item() method handles empty queue safely
        type_, uuid_, identifier, data = await self.queue.get_next_ready_item()
        if type_ is None:
            return

        try:
            if type_ == 'update_status':
                await self.handle_status_update(uuid_)
            elif type_ == 'chain_step':
                await self.handle_step(uuid_, identifier)
            elif type_ == 'check_update' and self.status_update_handler.app.type != 'telegram':
                await self.handle_check_update(identifier)
            elif type_ == 'alert':
                await self.handle_alert(data)
        except Exception as e:
            logger.error(f"Error handling queue item {type_}: {e}")
        
        # Always yield control after processing an item
        await asyncio.sleep(0)

    async def start_processing(self):
        """Start the background queue processing task"""
        if self._running:
            return
            
        self._running = True
        self._task = asyncio.create_task(self._process_queue_loop())
        logger.info("Started async queue processing")

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
                pass
        logger.info("Stopped async queue processing")

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
