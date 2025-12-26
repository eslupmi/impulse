import asyncio
import os
import shutil
import socket
import time
from pathlib import Path
from typing import Optional, Tuple

from app.config.config import get_config
from app.logging import logger


class FileLock:
    """
    File-based distributed lock for High Availability deployments.
    
    Uses a directory-based lock with heartbeat mechanism to detect stale locks.
    Designed for network filesystems where multiple instances may run simultaneously.
    
    Note: For reliable operation on network filesystems, ensure:
    - NTP is configured for time synchronization between hosts
    - STALE_SEC > HEARTBEAT_SEC * 2 for adequate safety margin
    """
    HEARTBEAT_SEC = 6
    STALE_SEC = 18
    MAX_HEARTBEAT_FAILURES = 3

    def __init__(self):
        config = get_config()
        self.lock_dir = Path(f"{config.data_path}/.lock.d")
        self.heartbeat_path = self.lock_dir / "heartbeat"
        self.pid_path = self.lock_dir / "pid"
        self.host_path = self.lock_dir / "host"
        self._active = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._heartbeat_failures = 0
        self._hostname = socket.gethostname()
        self._pid = os.getpid()

    def _cleanup_stale_lock(self) -> bool:
        """
        Remove stale lock directory if it exists and is stale.
        
        Returns:
            True if cleanup was successful or not needed, False if cleanup failed
            or lock is still active.
        """
        if not self.lock_dir.exists():
            return True
            
        if self.is_locked():
            return False
            
        logger.debug("Removing stale lock")
        try:
            for path in [self.heartbeat_path, self.pid_path, self.host_path]:
                try:
                    path.unlink(missing_ok=True)
                except (OSError, IOError):
                    pass
            
            try:
                self.lock_dir.rmdir()
            except OSError:
                if not self.is_locked():
                    shutil.rmtree(self.lock_dir, ignore_errors=True)
            return True
        except (OSError, IOError) as e:
            logger.warning(f"Stale lock cleanup failed: {e}")
            return False

    def acquire_lock(self) -> bool:
        """
        Attempt to acquire the lock.
        
        Returns:
            True if lock was successfully acquired, False otherwise.
        """
        try:
            self._cleanup_stale_lock()
            self.lock_dir.mkdir(parents=True, exist_ok=False)
            
            locktime = time.time()
            
            try:
                with open(self.heartbeat_path, "w") as f:
                    f.write(str(locktime))
                with open(self.pid_path, "w") as f:
                    f.write(str(self._pid))
                with open(self.host_path, "w") as f:
                    f.write(self._hostname)
            except (OSError, IOError) as e:
                logger.error(f"Lock file write failed: {e}")
                self._cleanup_failed_acquisition()
                return False
            
            if not self._verify_ownership():
                logger.error("Ownership verification failed")
                self._cleanup_failed_acquisition()
                return False
            
            self._active = True
            self._heartbeat_failures = 0
            try:
                loop = asyncio.get_running_loop()
                self._heartbeat_task = loop.create_task(self._heartbeat())
            except RuntimeError:
                logger.warning("Event loop not running")
            
            logger.debug("Lock acquired")
            return True
            
        except FileExistsError:
            logger.debug("Lock held by another instance")
            return False
        except (OSError, IOError) as e:
            logger.error(f"Lock acquisition failed: {e}")
            return False

    def _cleanup_failed_acquisition(self):
        """Clean up after a failed lock acquisition attempt."""
        try:
            if self.lock_dir.exists():
                shutil.rmtree(self.lock_dir, ignore_errors=True)
        except (OSError, IOError):
            pass

    def _verify_ownership(self) -> bool:
        """
        Verify that this instance owns the lock.
        
        Returns:
            True if this instance owns the lock, False otherwise.
        """
        try:
            hostname = self.host_path.read_text().strip()
            pid = self.pid_path.read_text().strip()
            return hostname == self._hostname and pid == str(self._pid)
        except (FileNotFoundError, OSError, IOError):
            return False

    async def release_lock(self):
        """Release the lock and stop heartbeat."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            self._heartbeat_task = None
        
        self._active = False
        
        if self.lock_dir.exists():
            try:
                shutil.rmtree(self.lock_dir)
                logger.info("Lock released")
            except (OSError, IOError) as e:
                logger.warning(f"Lock release failed: {e}")

    def release_lock_sync(self):
        """Synchronous version of release_lock for use outside async context."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
        
        self._active = False
        
        if self.lock_dir.exists():
            try:
                shutil.rmtree(self.lock_dir)
                logger.info("Lock released")
            except (OSError, IOError) as e:
                logger.warning(f"Lock release failed: {e}")

    def is_locked(self) -> bool:
        """
        Check if the lock is currently held by any instance.
        
        Returns:
            True if lock exists and heartbeat is fresh, False otherwise.
        """
        if not self.lock_dir.exists():
            return False
        try:
            locktime = float(self.heartbeat_path.read_text().strip())
            elapsed = time.time() - locktime
            return elapsed <= self.STALE_SEC
        except FileNotFoundError:
            return False
        except (ValueError, OSError) as e:
            logger.error(f"Heartbeat read failed: {e}")
            return False

    def is_owner(self) -> bool:
        """
        Check if this instance owns the lock.
        
        Returns:
            True if this instance owns and actively holds the lock.
        """
        return self._active and self._verify_ownership()

    def get_lock_info(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Get information about the current lock holder.
        
        Returns:
            Tuple of (hostname, pid, locktime) or (None, None, None) if not available.
        """
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
        """Wait until the lock becomes available."""
        while self.is_locked():
            await asyncio.sleep(1)

    async def _heartbeat(self):
        """Background task to update heartbeat while lock is held."""
        while self._active:
            success = self._update()
            if not success:
                self._heartbeat_failures += 1
                logger.warning(f"Heartbeat failed: {self._heartbeat_failures}/{self.MAX_HEARTBEAT_FAILURES}")
                if self._heartbeat_failures >= self.MAX_HEARTBEAT_FAILURES:
                    logger.error("Too many heartbeat failures")
                    self._active = False
                    break
            else:
                self._heartbeat_failures = 0
            
            await asyncio.sleep(self.HEARTBEAT_SEC)

    def _update(self) -> bool:
        """
        Update the heartbeat file.
        
        Returns:
            True if update was successful, False otherwise.
        """
        if not self._verify_ownership():
            logger.error("Ownership lost")
            return False
        
        locktime = time.time()
        try:
            with open(self.heartbeat_path, "w") as f:
                f.write(str(locktime))
            return True
        except (OSError, IOError) as e:
            logger.debug(f"Heartbeat update failed: {e}")
            return False
