import asyncio
import os
import shutil
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
        self.lock_dir = Path(f"{config.data_path}/.lock.d")
        self.heartbeat_path = self.lock_dir / "heartbeat"
        self.pid_path = self.lock_dir / "pid"
        self.host_path = self.lock_dir / "host"
        self._active = False
        self._heartbeat_task = None

    def acquire_lock(self):
        try:
            self.lock_dir.mkdir(parents=True, exist_ok=False)
            hostname = socket.gethostname()
            pid = os.getpid()
            locktime = time.time()
            
            with open(self.heartbeat_path, "w") as f:
                f.write(str(locktime))
            with open(self.pid_path, "w") as f:
                f.write(str(pid))
            with open(self.host_path, "w") as f:
                f.write(hostname)
            self._active = True
            loop = asyncio.get_running_loop()
            self._heartbeat_task = loop.create_task(self._heartbeat())
        except (OSError, IOError) as e:
            logger.debug(f"Error creating lock files: {e}")

    def release_lock(self):
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._active = False
        if self.lock_dir.exists():
            shutil.rmtree(self.lock_dir)

    def is_locked(self):
        if not self.lock_dir.exists():
            return False
        try:
            locktime = float(self.heartbeat_path.read_text().strip())
            updated = (time.time() - locktime) < self.STALE_SEC
            return updated
        except FileNotFoundError:
            return False
        except (ValueError, OSError) as e:
            logger.error(f"Error reading lock heartbeat file: {e}")
            return True

    def get_lock_info(self):
        try:
            hostname = self.host_path.read_text().strip()
            pid = self.pid_path.read_text().strip()
            locktime = self.heartbeat_path.read_text().strip()
            return hostname, pid, locktime
        except FileNotFoundError:
            return None, None, None
        except (ValueError, OSError):
            return None, None, None

    async def wait_for_unlock(self):
        while self.is_locked():
            await asyncio.sleep(1)

    async def _heartbeat(self):
        while self._active:
            self._update()
            await asyncio.sleep(self.HEARTBEAT_SEC)

    def _update(self):
        locktime = time.time()
        try:
            with open(self.heartbeat_path, "w") as f:
                f.write(str(locktime))
        except (OSError, IOError) as e:
            logger.debug(f"Error updating heartbeat file: {e}")
