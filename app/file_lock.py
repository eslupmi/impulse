import asyncio
import os
import socket
import time
from pathlib import Path
from app.config.config import get_config
from app.logging import logger


class FileLock:
    HEARTBEAT_SEC = 6
    STALE_SEC = 10

    def __init__(self):
        config = get_config()
        self.lock_path = Path(f"{config.data_path}/.lock")
        self._active = False
        self._heartbeat_task = None

    def lock(self):
        self._active = True
        self._update()
        loop = asyncio.get_running_loop()
        self._heartbeat_task = loop.create_task(self._heartbeat())

    def unlock(self):
        self._active = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self.lock_path.exists():
            os.remove(self.lock_path)

    def is_locked(self):
        if self.lock_path.exists():
            try:
                _, _, locktime = self.lock_path.read_text().strip().split(",")
                updated = (time.time() - float(locktime)) < self.STALE_SEC
                if updated:
                    return True
                else:
                    return False
            except (ValueError, FileNotFoundError) as e:
                logger.debug(f"Error reading lock file: {e}")
                return True
        return False

    def get_lock_info(self):
        if self.lock_path.exists():
            try:
                hostname, pid, locktime = self.lock_path.read_text().strip().split(",")
                return hostname, pid, locktime
            except (ValueError, FileNotFoundError):
                return None, None, None
        return None, None, None

    async def wait_for_unlock(self):
        while self.is_locked():
            await asyncio.sleep(1)

    async def _heartbeat(self):
        while self._active:
            self._update()
            await asyncio.sleep(self.HEARTBEAT_SEC)

    def _update(self):
        hostname = socket.gethostname()
        with open(self.lock_path, "w") as f:
            f.write(f"{hostname},{os.getpid()},{time.time()}")
