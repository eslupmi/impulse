import asyncio
import os
import socket
import time
from pathlib import Path
from app.config.config import get_config
from app.logging import logger


class FileLock:
    HEARTBEAT_SEC = 10
    STALE_SEC = 30
    
    def __init__(self):
        config = get_config()
        self.lock_path = Path(f"{config.data_path}/.lock")
        self._running = True
    
    def locked(self):
        if self.lock_path.exists():
            try:
                hostname, pid, locktime = self.lock_path.read_text().strip().split(",")
                stale = (time.time() - float(locktime)) > self.STALE_SEC
                if stale:
                    logger.debug(f"Lock file is stale (held by {hostname}, PID {pid}), considering unlocked")
                    return False
            except (ValueError, FileNotFoundError) as e:
                logger.debug(f"Error reading lock file: {e}, considering unlocked")
                return False
        return True
    
    async def wait_for_unlock(self):
        while self.locked():
            await asyncio.sleep(1)
    
    async def heartbeat(self):
        while self._running:
            self._update_lock()
            await asyncio.sleep(self.HEARTBEAT_SEC)
    
    def _update_lock(self):
        hostname = socket.gethostname()
        with open(self.lock_path, "w") as f:
            f.write(f"{hostname},{os.getpid()},{time.time()}")
    
    def release_lock(self):
        self._running = False
        if self.lock_path.exists():
            os.remove(self.lock_path)
