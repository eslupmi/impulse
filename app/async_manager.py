import asyncio
import threading
from typing import Optional, List

from app.logging import logger


class AsyncManager:
    _instance: Optional['AsyncManager'] = None
    _loop: Optional[asyncio.AbstractEventLoop] = None
    _thread: Optional[threading.Thread] = None
    _tasks: List[asyncio.Task] = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AsyncManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

    def start(self) -> None:
        """Start the event loop in a background thread."""
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run_event_loop, daemon=True)
            self._thread.start()
            logger.info("Started async event loop in background thread")

    def _run_event_loop(self) -> None:
        """Run the event loop forever."""
        logger.info("Event loop thread started")
        self._loop.run_forever()

    def get_loop(self) -> asyncio.AbstractEventLoop:
        """Get the event loop instance."""
        return self._loop

    def create_task(self, coro) -> asyncio.Task:
        """Create and schedule a new task in the event loop."""
        if not self._loop.is_running():
            logger.warning("Event loop is not running, task will not be scheduled")
            return None

        task = self._loop.create_task(coro)
        self._tasks.append(task)
        logger.info(f"Created new async task: {coro.__name__}")

        # Ensure the task is scheduled
        self._loop.call_soon_threadsafe(lambda: None)
        return task

    def shutdown(self) -> None:
        """Shutdown the event loop and its thread gracefully."""
        if self._loop is not None and self._loop.is_running():
            logger.info("Shutting down async event loop")

            try:
                # Get all running tasks
                pending = asyncio.all_tasks(self._loop)

                # Only proceed with task cancellation if there are tasks to cancel
                if pending:
                    # Cancel all running tasks with a timeout
                    for task in pending:
                        if not task.done():
                            task.cancel()
                            logger.info(f"Cancelling task: {task.get_name()}")

                    # Run the loop until all tasks are done, with a timeout
                    done, pending = self._loop.run_until_complete(
                        asyncio.wait(pending, timeout=5.0, return_when=asyncio.ALL_COMPLETED)
                    )

                    # Log any tasks that didn't complete
                    if pending:
                        logger.warning(f"Some tasks did not complete: {[t.get_name() for t in pending]}")
                else:
                    logger.info("No pending tasks to cancel")

                # Stop the loop
                self._loop.stop()

                # Wait for the background thread to finish with a timeout
                if self._thread is not None and self._thread.is_alive():
                    self._thread.join(timeout=5.0)
                    if self._thread.is_alive():
                        logger.warning("Event loop thread did not stop gracefully, forcing shutdown")
                        # Force the thread to stop if it's still alive
                        self._thread = None

                # Close the loop
                self._loop.close()
                self._loop = None
                self._tasks = []
                logger.info("Async event loop shutdown complete")

            except Exception as e:
                logger.error(f"Error during async shutdown: {str(e)}")
                # Force cleanup in case of error
                self._loop = None
                self._thread = None
                self._tasks = []

    @classmethod
    def get_instance(cls) -> 'AsyncManager':
        """Get the singleton instance of AsyncManager."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
