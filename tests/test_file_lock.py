"""
Unit tests for app.file_lock module.
"""
import asyncio
import os
import socket
import time
from pathlib import Path
from unittest.mock import Mock, patch, mock_open, MagicMock, AsyncMock

import pytest

from app.file_lock import FileLock


class TestFileLockInit:
    """Test cases for FileLock initialization."""

    def test_init_creates_lock_dir(self):
        """Test that __init__ creates correct lock directory."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config:
            mock_config = Mock()
            mock_config.data_path = "/test/data/path"
            mock_get_env_config.return_value = mock_config

            file_lock = FileLock()

            assert file_lock.lock_dir == Path("/test/data/path/.lock.d")
            assert file_lock.heartbeat_path == Path("/test/data/path/.lock.d/heartbeat")
            assert file_lock.pid_path == Path("/test/data/path/.lock.d/pid")
            assert file_lock.host_path == Path("/test/data/path/.lock.d/host")
            assert file_lock._active is False
            assert file_lock._heartbeat_task is None

    def test_init_with_different_data_paths(self):
        """Test initialization with different data paths."""
        test_paths = [
            "/tmp/test",
            "/var/lib/impulse",
            "./relative/path",
            "data"
        ]

        for data_path in test_paths:
            with patch('app.file_lock.get_environment_config') as mock_get_env_config:
                mock_config = Mock()
                mock_config.data_path = data_path
                mock_get_env_config.return_value = mock_config

                file_lock = FileLock()

                assert file_lock.lock_dir == Path(f"{data_path}/.lock.d")
                assert file_lock.heartbeat_path == Path(f"{data_path}/.lock.d/heartbeat")
                assert file_lock.pid_path == Path(f"{data_path}/.lock.d/pid")
                assert file_lock.host_path == Path(f"{data_path}/.lock.d/host")


class TestFileLockAcquireLock:
    """Test cases for acquire_lock method."""

    @pytest.mark.asyncio
    async def test_acquire_lock_creates_directory_and_returns_true(self):
        """Test that acquire_lock creates lock directory and returns True on success."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('app.file_lock.socket.gethostname', return_value='test-host'), \
             patch('app.file_lock.os.getpid', return_value=12345), \
             patch('app.file_lock.time.time', return_value=1000.0), \
             patch('pathlib.Path.exists', return_value=False), \
             patch('pathlib.Path.mkdir') as mock_mkdir, \
             patch('pathlib.Path.read_text') as mock_read_text, \
             patch('builtins.open', mock_open()) as mock_file, \
             patch('asyncio.get_running_loop') as mock_get_loop:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config
            
            # Mock read_text for ownership verification
            mock_read_text.side_effect = ["test-host", "12345"]
            
            mock_loop = Mock()
            mock_task = Mock()
            mock_loop.create_task.return_value = mock_task
            mock_get_loop.return_value = mock_loop

            file_lock = FileLock()
            result = file_lock.acquire_lock()

            assert result is True
            assert file_lock._active is True
            assert file_lock._heartbeat_task == mock_task
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=False)
            # Should be called 3 times for heartbeat, pid, and host files
            assert mock_file.call_count == 3
            mock_loop.create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_acquire_lock_writes_correct_content(self):
        """Test that acquire_lock writes correct content to three files on initial creation."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('app.file_lock.socket.gethostname', return_value='test-hostname'), \
             patch('app.file_lock.os.getpid', return_value=9999), \
             patch('app.file_lock.time.time', return_value=1234.567), \
             patch('pathlib.Path.exists', return_value=False), \
             patch('pathlib.Path.mkdir') as mock_mkdir, \
             patch('pathlib.Path.read_text') as mock_read_text, \
             patch('builtins.open', mock_open()) as mock_file, \
             patch('asyncio.get_running_loop') as mock_get_loop:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config
            
            # Mock read_text for ownership verification
            mock_read_text.side_effect = ["test-hostname", "9999"]
            
            mock_loop = Mock()
            mock_task = Mock()
            mock_loop.create_task.return_value = mock_task
            mock_get_loop.return_value = mock_loop

            file_lock = FileLock()
            result = file_lock.acquire_lock()

            assert result is True
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=False)
            # Should be called 3 times for heartbeat, pid, and host files
            assert mock_file.call_count == 3
            # Check write calls
            write_calls = [str(call[0][0]) for call in mock_file().write.call_args_list]
            assert "1234.567" in write_calls
            assert "9999" in write_calls
            assert "test-hostname" in write_calls

    @pytest.mark.asyncio
    async def test_acquire_lock_handles_write_error_returns_false(self):
        """Test that acquire_lock handles write errors and returns False."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('app.file_lock.socket.gethostname', return_value='test-host'), \
             patch('app.file_lock.os.getpid', return_value=12345), \
             patch('app.file_lock.time.time', return_value=1000.0), \
             patch('pathlib.Path.exists', return_value=False), \
             patch('pathlib.Path.mkdir'), \
             patch('builtins.open', side_effect=OSError("Permission denied")), \
             patch('app.file_lock.logger') as mock_logger, \
             patch('app.file_lock.shutil.rmtree'), \
             patch('asyncio.get_running_loop') as mock_get_loop:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config
            
            mock_loop = Mock()
            mock_get_loop.return_value = mock_loop

            file_lock = FileLock()
            result = file_lock.acquire_lock()

            assert result is False
            assert file_lock._active is False
            assert file_lock._heartbeat_task is None
            mock_logger.error.assert_called()
            mock_get_loop.assert_not_called()

    @pytest.mark.asyncio
    async def test_acquire_lock_fails_when_directory_exists_returns_false(self):
        """Test that acquire_lock returns False when directory already exists."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('pathlib.Path.exists', return_value=False), \
             patch('pathlib.Path.mkdir', side_effect=FileExistsError("Directory exists")), \
             patch('app.file_lock.logger') as mock_logger, \
             patch('asyncio.get_running_loop') as mock_get_loop:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            file_lock = FileLock()
            result = file_lock.acquire_lock()

            assert result is False
            assert file_lock._active is False
            assert file_lock._heartbeat_task is None
            mock_logger.debug.assert_called()
            mock_get_loop.assert_not_called()

    @pytest.mark.asyncio
    async def test_acquire_lock_fails_on_mkdir_error_returns_false(self):
        """Test that acquire_lock returns False when mkdir raises OSError."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('pathlib.Path.exists', return_value=False), \
             patch('pathlib.Path.mkdir', side_effect=OSError("Permission denied")), \
             patch('app.file_lock.logger') as mock_logger, \
             patch('asyncio.get_running_loop') as mock_get_loop:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            file_lock = FileLock()
            result = file_lock.acquire_lock()

            assert result is False
            assert file_lock._active is False
            assert file_lock._heartbeat_task is None
            mock_logger.error.assert_called()
            mock_get_loop.assert_not_called()


class TestFileLockReleaseLock:
    """Test cases for release_lock method (now async)."""

    @pytest.mark.asyncio
    async def test_release_lock_removes_directory(self):
        """Test that release_lock removes lock directory."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('pathlib.Path.exists', return_value=True), \
             patch('app.file_lock.shutil.rmtree') as mock_rmtree:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            async def cancelled_task():
                raise asyncio.CancelledError()
            
            file_lock = FileLock()
            file_lock._heartbeat_task = asyncio.create_task(cancelled_task())
            file_lock._active = True
            
            await file_lock.release_lock()

            assert file_lock._active is False
            mock_rmtree.assert_called_once_with(file_lock.lock_dir)

    @pytest.mark.asyncio
    async def test_release_lock_cancels_heartbeat_task(self):
        """Test that release_lock cancels and awaits heartbeat task."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('pathlib.Path.exists', return_value=False):
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            task_started = asyncio.Event()
            
            async def long_running_task():
                task_started.set()
                await asyncio.sleep(1000)
            
            file_lock = FileLock()
            file_lock._heartbeat_task = asyncio.create_task(long_running_task())
            file_lock._active = True
            
            await task_started.wait()

            await file_lock.release_lock()

            assert file_lock._active is False
            assert file_lock._heartbeat_task is None
            assert file_lock._heartbeat_task is None

    @pytest.mark.asyncio
    async def test_release_lock_without_heartbeat_task(self):
        """Test release_lock when heartbeat task doesn't exist."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('pathlib.Path.exists', return_value=False):
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            file_lock = FileLock()
            file_lock._heartbeat_task = None
            file_lock._active = True

            await file_lock.release_lock()

            # _active should be set to False even without heartbeat task
            assert file_lock._active is False

    @pytest.mark.asyncio
    async def test_release_lock_when_directory_not_exists(self):
        """Test release_lock when lock directory doesn't exist."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('pathlib.Path.exists', return_value=False), \
             patch('app.file_lock.shutil.rmtree') as mock_rmtree:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            file_lock = FileLock()
            await file_lock.release_lock()

            mock_rmtree.assert_not_called()

    def test_release_lock_sync_removes_directory(self):
        """Test that release_lock_sync removes lock directory."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('pathlib.Path.exists', return_value=True), \
             patch('app.file_lock.shutil.rmtree') as mock_rmtree:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            mock_task = Mock()
            file_lock = FileLock()
            file_lock._heartbeat_task = mock_task
            file_lock._active = True
            
            file_lock.release_lock_sync()

            assert file_lock._active is False
            mock_rmtree.assert_called_once_with(file_lock.lock_dir)


class TestFileLockIsLocked:
    """Test cases for is_locked method."""

    def test_is_locked_returns_false_when_directory_not_exists(self):
        """Test is_locked returns False when lock directory doesn't exist."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('pathlib.Path.exists', return_value=False):
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            file_lock = FileLock()
            assert file_lock.is_locked() is False

    def test_is_locked_returns_true_when_file_fresh(self):
        """Test is_locked returns True when lock heartbeat file is fresh."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.read_text', return_value="1000.0"), \
             patch('app.file_lock.time.time', return_value=1005.0):
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            file_lock = FileLock()
            assert file_lock.is_locked() is True

    def test_is_locked_returns_false_when_file_stale(self):
        """Test is_locked returns False when lock heartbeat file is stale."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.read_text', return_value="1000.0"), \
             patch('app.file_lock.time.time', return_value=1019.0):  # STALE_SEC is now 18
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            file_lock = FileLock()
            assert file_lock.is_locked() is False

    def test_is_locked_handles_value_error(self):
        """Test is_locked handles ValueError when parsing lock heartbeat file."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.read_text', return_value="invalid"), \
             patch('app.file_lock.logger') as mock_logger:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            file_lock = FileLock()
            result = file_lock.is_locked()

            # Now returns False on error for safer HA recovery
            assert result is False
            mock_logger.error.assert_called()

    def test_is_locked_handles_file_not_found_error(self):
        """Test is_locked handles FileNotFoundError."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('pathlib.Path.read_text', side_effect=FileNotFoundError()):
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            file_lock = FileLock()
            result = file_lock.is_locked()

            assert result is False  # Returns False when file not found

    def test_is_locked_boundary_condition_at_stale_sec(self):
        """Test is_locked with boundary condition (exactly STALE_SEC)."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.read_text', return_value="1000.0"), \
             patch('app.file_lock.time.time', return_value=1018.0):  # Exactly STALE_SEC (18)
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            file_lock = FileLock()
            # At exactly STALE_SEC, should still be considered locked (<=)
            assert file_lock.is_locked() is True

    def test_is_locked_boundary_condition_past_stale_sec(self):
        """Test is_locked with boundary condition (just past STALE_SEC)."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.read_text', return_value="1000.0"), \
             patch('app.file_lock.time.time', return_value=1018.001):  # Just past STALE_SEC
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            file_lock = FileLock()
            assert file_lock.is_locked() is False


class TestFileLockIsOwner:
    """Test cases for is_owner method."""

    def test_is_owner_returns_true_when_owner(self):
        """Test is_owner returns True when this instance owns the lock."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('app.file_lock.socket.gethostname', return_value='test-host'), \
             patch('app.file_lock.os.getpid', return_value=12345), \
             patch('pathlib.Path.read_text') as mock_read_text:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config
            
            # Return hostname and pid that match
            mock_read_text.side_effect = ["test-host", "12345"]

            file_lock = FileLock()
            file_lock._active = True
            
            assert file_lock.is_owner() is True

    def test_is_owner_returns_false_when_not_active(self):
        """Test is_owner returns False when not active."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            file_lock = FileLock()
            file_lock._active = False
            
            assert file_lock.is_owner() is False

    def test_is_owner_returns_false_when_different_owner(self):
        """Test is_owner returns False when different instance owns lock."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('app.file_lock.socket.gethostname', return_value='test-host'), \
             patch('app.file_lock.os.getpid', return_value=12345), \
             patch('pathlib.Path.read_text') as mock_read_text:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config
            
            # Return different hostname/pid
            mock_read_text.side_effect = ["other-host", "99999"]

            file_lock = FileLock()
            file_lock._active = True
            
            assert file_lock.is_owner() is False


class TestFileLockGetLockInfo:
    """Test cases for get_lock_info method."""

    def test_get_lock_info_returns_none_when_file_not_exists(self):
        """Test get_lock_info returns None when lock heartbeat file doesn't exist."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('pathlib.Path.read_text', side_effect=FileNotFoundError()):
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            file_lock = FileLock()
            hostname, pid, locktime = file_lock.get_lock_info()

            assert hostname is None
            assert pid is None
            assert locktime is None

    def test_get_lock_info_returns_correct_info(self):
        """Test get_lock_info returns correct information."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config:
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            file_lock = FileLock()
            
            # Mock read_text for each path separately
            # Since read_text is called on Path instances, we need to patch it at the class level
            # and use side_effect to return different values for each call
            with patch('pathlib.Path.read_text') as mock_read_text:
                # read_text is called 3 times: host_path, pid_path, heartbeat_path
                # Return values in the order they are called
                mock_read_text.side_effect = ["test-hostname", "12345", "1000.5"]
                
                hostname, pid, locktime = file_lock.get_lock_info()

                assert hostname == "test-hostname"
                assert pid == "12345"
                assert locktime == "1000.5"
                # Verify read_text was called 3 times
                assert mock_read_text.call_count == 3

    def test_get_lock_info_handles_value_error(self):
        """Test get_lock_info handles ValueError."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('pathlib.Path.read_text', side_effect=ValueError("Invalid format")):
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            file_lock = FileLock()
            hostname, pid, locktime = file_lock.get_lock_info()

            assert hostname is None
            assert pid is None
            assert locktime is None

    def test_get_lock_info_handles_file_not_found_error(self):
        """Test get_lock_info handles FileNotFoundError."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('pathlib.Path.read_text', side_effect=FileNotFoundError()):
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            file_lock = FileLock()
            hostname, pid, locktime = file_lock.get_lock_info()

            assert hostname is None
            assert pid is None
            assert locktime is None


class TestFileLockWaitForUnlock:
    """Test cases for wait_for_unlock method."""

    @pytest.mark.asyncio
    async def test_wait_for_unlock_returns_immediately_when_unlocked(self):
        """Test wait_for_unlock returns immediately when not locked."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch.object(FileLock, 'is_locked', return_value=False):
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            file_lock = FileLock()
            await file_lock.wait_for_unlock()

            # Should return immediately without sleeping

    @pytest.mark.asyncio
    async def test_wait_for_unlock_waits_when_locked(self):
        """Test wait_for_unlock waits when locked."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch.object(FileLock, 'is_locked', side_effect=[True, True, False]), \
             patch('asyncio.sleep') as mock_sleep:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            file_lock = FileLock()
            await file_lock.wait_for_unlock()

            assert mock_sleep.call_count == 2
            mock_sleep.assert_called_with(1)


class TestFileLockUpdate:
    """Test cases for _update method."""

    def test_update_writes_heartbeat_and_returns_true(self):
        """Test _update writes heartbeat file and returns True on success."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('app.file_lock.socket.gethostname', return_value='test-host'), \
             patch('app.file_lock.os.getpid', return_value=12345), \
             patch('app.file_lock.time.time', return_value=2000.123), \
             patch('pathlib.Path.read_text') as mock_read_text, \
             patch('builtins.open', mock_open()) as mock_file:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config
            
            # Mock ownership verification
            mock_read_text.side_effect = ["test-host", "12345"]

            file_lock = FileLock()
            result = file_lock._update()

            assert result is True
            # Should be called only once for heartbeat file
            assert mock_file.call_count == 1
            # Check write call
            write_calls = [str(call[0][0]) for call in mock_file().write.call_args_list]
            assert "2000.123" in write_calls

    def test_update_returns_false_when_ownership_lost(self):
        """Test _update returns False when ownership is lost."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('app.file_lock.socket.gethostname', return_value='test-host'), \
             patch('app.file_lock.os.getpid', return_value=12345), \
             patch('pathlib.Path.read_text') as mock_read_text, \
             patch('app.file_lock.logger') as mock_logger:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config
            
            # Return different owner
            mock_read_text.side_effect = ["other-host", "99999"]

            file_lock = FileLock()
            result = file_lock._update()

            assert result is False
            mock_logger.error.assert_called()

    def test_update_handles_oserror_returns_false(self):
        """Test _update handles OSError and returns False."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('app.file_lock.socket.gethostname', return_value='test-host'), \
             patch('app.file_lock.os.getpid', return_value=12345), \
             patch('app.file_lock.time.time', return_value=1000.0), \
             patch('pathlib.Path.read_text') as mock_read_text, \
             patch('builtins.open', side_effect=OSError("Permission denied")), \
             patch('app.file_lock.logger') as mock_logger:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config
            
            # Mock ownership verification to pass
            mock_read_text.side_effect = ["test-host", "12345"]

            file_lock = FileLock()
            result = file_lock._update()

            assert result is False
            mock_logger.debug.assert_called()

    def test_update_handles_ioerror_returns_false(self):
        """Test _update handles IOError and returns False."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('app.file_lock.socket.gethostname', return_value='test-host'), \
             patch('app.file_lock.os.getpid', return_value=12345), \
             patch('app.file_lock.time.time', return_value=1000.0), \
             patch('pathlib.Path.read_text') as mock_read_text, \
             patch('builtins.open', side_effect=IOError("Disk full")), \
             patch('app.file_lock.logger') as mock_logger:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config
            
            # Mock ownership verification to pass
            mock_read_text.side_effect = ["test-host", "12345"]

            file_lock = FileLock()
            result = file_lock._update()

            assert result is False
            mock_logger.debug.assert_called()


class TestFileLockHeartbeat:
    """Test cases for _heartbeat method."""

    @pytest.mark.asyncio
    async def test_heartbeat_updates_while_active(self):
        """Test _heartbeat updates lock file while active."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch.object(FileLock, '_update', return_value=True) as mock_update, \
             patch('app.file_lock.asyncio.sleep') as mock_sleep:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            file_lock = FileLock()
            file_lock._active = True

            # Make sleep stop the loop after first iteration
            call_count = 0
            def mock_sleep_side_effect(delay):
                nonlocal call_count
                call_count += 1
                if call_count >= 1:
                    file_lock._active = False
            
            mock_sleep.side_effect = mock_sleep_side_effect

            # Start heartbeat task
            task = asyncio.create_task(file_lock._heartbeat())
            
            try:
                await task
            except asyncio.CancelledError:
                pass
            
            # Verify update was called
            assert mock_update.called

    @pytest.mark.asyncio
    async def test_heartbeat_stops_when_inactive(self):
        """Test _heartbeat stops when _active is False."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch.object(FileLock, '_update', return_value=True) as mock_update, \
             patch('app.file_lock.asyncio.sleep'):
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            file_lock = FileLock()
            file_lock._active = False

            # Start heartbeat task - should exit immediately since _active is False
            task = asyncio.create_task(file_lock._heartbeat())
            
            try:
                await task
            except asyncio.CancelledError:
                pass
            
            # Update should not be called if _active is False from start
            assert not mock_update.called

    @pytest.mark.asyncio
    async def test_heartbeat_sleeps_correct_interval(self):
        """Test _heartbeat sleeps for HEARTBEAT_SEC seconds."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch.object(FileLock, '_update', return_value=True), \
             patch('app.file_lock.asyncio.sleep') as mock_sleep:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            file_lock = FileLock()
            file_lock._active = True

            # Make sleep stop the loop after first iteration
            call_count = 0
            def mock_sleep_side_effect(delay):
                nonlocal call_count
                call_count += 1
                # Verify it's called with HEARTBEAT_SEC
                assert delay == FileLock.HEARTBEAT_SEC
                if call_count >= 1:
                    file_lock._active = False
            
            mock_sleep.side_effect = mock_sleep_side_effect

            # Start heartbeat task
            task = asyncio.create_task(file_lock._heartbeat())
            
            try:
                await task
            except asyncio.CancelledError:
                pass
            
            # Verify sleep was called
            assert mock_sleep.called

    @pytest.mark.asyncio
    async def test_heartbeat_stops_after_max_failures(self):
        """Test _heartbeat stops after MAX_HEARTBEAT_FAILURES consecutive failures."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch.object(FileLock, '_update', return_value=False) as mock_update, \
             patch('app.file_lock.asyncio.sleep') as mock_sleep, \
             patch('app.file_lock.logger') as mock_logger:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            file_lock = FileLock()
            file_lock._active = True

            # Start heartbeat task
            task = asyncio.create_task(file_lock._heartbeat())
            
            try:
                await task
            except asyncio.CancelledError:
                pass
            
            # Should have called update MAX_HEARTBEAT_FAILURES times
            assert mock_update.call_count == FileLock.MAX_HEARTBEAT_FAILURES
            # Should have stopped due to failures
            assert file_lock._active is False
            # Should have logged error
            mock_logger.error.assert_called()


class TestFileLockConstants:
    """Test cases for FileLock constants."""

    def test_heartbeat_sec_constant(self):
        """Test HEARTBEAT_SEC constant value."""
        assert FileLock.HEARTBEAT_SEC == 6

    def test_stale_sec_constant(self):
        """Test STALE_SEC constant value (should be 3x HEARTBEAT_SEC for safety)."""
        assert FileLock.STALE_SEC == 18
        assert FileLock.STALE_SEC >= FileLock.HEARTBEAT_SEC * 2

    def test_max_heartbeat_failures_constant(self):
        """Test MAX_HEARTBEAT_FAILURES constant value."""
        assert FileLock.MAX_HEARTBEAT_FAILURES == 3


class TestFileLockVerifyOwnership:
    """Test cases for _verify_ownership method."""

    def test_verify_ownership_returns_true_when_owner(self):
        """Test _verify_ownership returns True when this instance owns the lock."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('app.file_lock.socket.gethostname', return_value='test-host'), \
             patch('app.file_lock.os.getpid', return_value=12345), \
             patch('pathlib.Path.read_text') as mock_read_text:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config
            
            mock_read_text.side_effect = ["test-host", "12345"]

            file_lock = FileLock()
            assert file_lock._verify_ownership() is True

    def test_verify_ownership_returns_false_when_different_host(self):
        """Test _verify_ownership returns False when hostname differs."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('app.file_lock.socket.gethostname', return_value='test-host'), \
             patch('app.file_lock.os.getpid', return_value=12345), \
             patch('pathlib.Path.read_text') as mock_read_text:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config
            
            mock_read_text.side_effect = ["other-host", "12345"]

            file_lock = FileLock()
            assert file_lock._verify_ownership() is False

    def test_verify_ownership_returns_false_when_different_pid(self):
        """Test _verify_ownership returns False when PID differs."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('app.file_lock.socket.gethostname', return_value='test-host'), \
             patch('app.file_lock.os.getpid', return_value=12345), \
             patch('pathlib.Path.read_text') as mock_read_text:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config
            
            mock_read_text.side_effect = ["test-host", "99999"]

            file_lock = FileLock()
            assert file_lock._verify_ownership() is False

    def test_verify_ownership_returns_false_on_file_not_found(self):
        """Test _verify_ownership returns False when files don't exist."""
        with patch('app.file_lock.get_environment_config') as mock_get_env_config, \
             patch('pathlib.Path.read_text', side_effect=FileNotFoundError()):
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_env_config.return_value = mock_config

            file_lock = FileLock()
            assert file_lock._verify_ownership() is False
