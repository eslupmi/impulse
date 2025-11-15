"""
Unit tests for app.file_lock module.
"""
import asyncio
import os
import socket
import time
from pathlib import Path
from unittest.mock import Mock, patch, mock_open, MagicMock

import pytest

from app.file_lock import FileLock


class TestFileLockInit:
    """Test cases for FileLock initialization."""

    def test_init_creates_lock_path(self):
        """Test that __init__ creates correct lock path."""
        with patch('app.file_lock.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.data_path = "/test/data/path"
            mock_get_config.return_value = mock_config

            file_lock = FileLock()

            assert file_lock.lock_path == Path("/test/data/path/.lock")
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
            with patch('app.file_lock.get_config') as mock_get_config:
                mock_config = Mock()
                mock_config.data_path = data_path
                mock_get_config.return_value = mock_config

                file_lock = FileLock()

                assert file_lock.lock_path == Path(f"{data_path}/.lock")


class TestFileLockAcquireLock:
    """Test cases for acquire_lock method."""

    @pytest.mark.asyncio
    async def test_acquire_lock_creates_file(self):
        """Test that acquire_lock creates lock file."""
        with patch('app.file_lock.get_config') as mock_get_config, \
             patch('app.file_lock.socket.gethostname', return_value='test-host'), \
             patch('app.file_lock.os.getpid', return_value=12345), \
             patch('app.file_lock.time.time', return_value=1000.0), \
             patch('builtins.open', mock_open()) as mock_file, \
             patch('asyncio.get_running_loop') as mock_get_loop:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_config.return_value = mock_config
            
            mock_loop = Mock()
            mock_task = Mock()
            mock_loop.create_task.return_value = mock_task
            mock_get_loop.return_value = mock_loop

            file_lock = FileLock()
            file_lock.acquire_lock()

            assert file_lock._active is True
            assert file_lock._heartbeat_task == mock_task
            mock_file.assert_called_once()
            mock_loop.create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_acquire_lock_writes_correct_content(self):
        """Test that acquire_lock writes correct content to lock file."""
        with patch('app.file_lock.get_config') as mock_get_config, \
             patch('app.file_lock.socket.gethostname', return_value='test-hostname'), \
             patch('app.file_lock.os.getpid', return_value=9999), \
             patch('app.file_lock.time.time', return_value=1234.567), \
             patch('builtins.open', mock_open()) as mock_file, \
             patch('asyncio.get_running_loop') as mock_get_loop:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_config.return_value = mock_config
            
            mock_loop = Mock()
            mock_task = Mock()
            mock_loop.create_task.return_value = mock_task
            mock_get_loop.return_value = mock_loop

            file_lock = FileLock()
            file_lock.acquire_lock()

            mock_file().write.assert_called_once_with("test-hostname,9999,1234.567")

    @pytest.mark.asyncio
    async def test_acquire_lock_handles_write_error(self):
        """Test that acquire_lock handles write errors gracefully."""
        with patch('app.file_lock.get_config') as mock_get_config, \
             patch('app.file_lock.socket.gethostname', return_value='test-host'), \
             patch('app.file_lock.os.getpid', return_value=12345), \
             patch('app.file_lock.time.time', return_value=1000.0), \
             patch('builtins.open', side_effect=OSError("Permission denied")), \
             patch('app.file_lock.logger') as mock_logger, \
             patch('asyncio.get_running_loop') as mock_get_loop:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_config.return_value = mock_config
            
            mock_loop = Mock()
            mock_task = Mock()
            mock_loop.create_task.return_value = mock_task
            mock_get_loop.return_value = mock_loop

            file_lock = FileLock()
            file_lock.acquire_lock()

            assert file_lock._active is True
            mock_logger.debug.assert_called()


class TestFileLockReleaseLock:
    """Test cases for release_lock method."""

    def test_release_lock_removes_file(self):
        """Test that release_lock removes lock file."""
        with patch('app.file_lock.get_config') as mock_get_config, \
             patch('pathlib.Path.exists', return_value=True), \
             patch('app.file_lock.os.remove') as mock_remove:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_config.return_value = mock_config

            file_lock = FileLock()
            file_lock._active = True
            file_lock.release_lock()

            assert file_lock._active is False
            mock_remove.assert_called_once()

    def test_release_lock_cancels_heartbeat_task(self):
        """Test that release_lock cancels heartbeat task."""
        with patch('app.file_lock.get_config') as mock_get_config, \
             patch('pathlib.Path.exists', return_value=False):
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_config.return_value = mock_config

            mock_task = Mock()
            file_lock = FileLock()
            file_lock._heartbeat_task = mock_task
            file_lock._active = True

            file_lock.release_lock()

            assert file_lock._active is False
            mock_task.cancel.assert_called_once()

    def test_release_lock_without_heartbeat_task(self):
        """Test release_lock when heartbeat task doesn't exist."""
        with patch('app.file_lock.get_config') as mock_get_config, \
             patch('pathlib.Path.exists', return_value=False):
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_config.return_value = mock_config

            file_lock = FileLock()
            file_lock._heartbeat_task = None
            file_lock._active = True

            file_lock.release_lock()

            assert file_lock._active is False

    def test_release_lock_when_file_not_exists(self):
        """Test release_lock when lock file doesn't exist."""
        with patch('app.file_lock.get_config') as mock_get_config, \
             patch('pathlib.Path.exists', return_value=False), \
             patch('app.file_lock.os.remove') as mock_remove:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_config.return_value = mock_config

            file_lock = FileLock()
            file_lock.release_lock()

            mock_remove.assert_not_called()


class TestFileLockIsLocked:
    """Test cases for is_locked method."""

    def test_is_locked_returns_false_when_file_not_exists(self):
        """Test is_locked returns False when lock file doesn't exist."""
        with patch('app.file_lock.get_config') as mock_get_config, \
             patch('pathlib.Path.exists', return_value=False):
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_config.return_value = mock_config

            file_lock = FileLock()
            assert file_lock.is_locked() is False

    def test_is_locked_returns_true_when_file_fresh(self):
        """Test is_locked returns True when lock file is fresh."""
        with patch('app.file_lock.get_config') as mock_get_config, \
             patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.read_text', return_value="hostname,12345,1000.0"), \
             patch('app.file_lock.time.time', return_value=1005.0):
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_config.return_value = mock_config

            file_lock = FileLock()
            assert file_lock.is_locked() is True

    def test_is_locked_returns_false_when_file_stale(self):
        """Test is_locked returns False when lock file is stale."""
        with patch('app.file_lock.get_config') as mock_get_config, \
             patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.read_text', return_value="hostname,12345,1000.0"), \
             patch('app.file_lock.time.time', return_value=1011.0):
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_config.return_value = mock_config

            file_lock = FileLock()
            assert file_lock.is_locked() is False

    def test_is_locked_handles_value_error(self):
        """Test is_locked handles ValueError when parsing lock file."""
        with patch('app.file_lock.get_config') as mock_get_config, \
             patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.read_text', return_value="invalid,format"), \
             patch('app.file_lock.logger') as mock_logger:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_config.return_value = mock_config

            file_lock = FileLock()
            result = file_lock.is_locked()

            assert result is True  # Returns True on error
            mock_logger.debug.assert_called()

    def test_is_locked_handles_file_not_found_error(self):
        """Test is_locked handles FileNotFoundError."""
        with patch('app.file_lock.get_config') as mock_get_config, \
             patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.read_text', side_effect=FileNotFoundError()), \
             patch('app.file_lock.logger') as mock_logger:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_config.return_value = mock_config

            file_lock = FileLock()
            result = file_lock.is_locked()

            assert result is True  # Returns True on error
            mock_logger.debug.assert_called()

    def test_is_locked_boundary_condition_stale(self):
        """Test is_locked with boundary condition (exactly STALE_SEC)."""
        with patch('app.file_lock.get_config') as mock_get_config, \
             patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.read_text', return_value="hostname,12345,1000.0"), \
             patch('app.file_lock.time.time', return_value=1010.0):
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_config.return_value = mock_config

            file_lock = FileLock()
            assert file_lock.is_locked() is False  # Exactly STALE_SEC, should be stale


class TestFileLockGetLockInfo:
    """Test cases for get_lock_info method."""

    def test_get_lock_info_returns_none_when_file_not_exists(self):
        """Test get_lock_info returns None when lock file doesn't exist."""
        with patch('app.file_lock.get_config') as mock_get_config, \
             patch('pathlib.Path.exists', return_value=False):
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_config.return_value = mock_config

            file_lock = FileLock()
            hostname, pid, locktime = file_lock.get_lock_info()

            assert hostname is None
            assert pid is None
            assert locktime is None

    def test_get_lock_info_returns_correct_info(self):
        """Test get_lock_info returns correct information."""
        with patch('app.file_lock.get_config') as mock_get_config, \
             patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.read_text', return_value="test-hostname,12345,1000.5"):
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_config.return_value = mock_config

            file_lock = FileLock()
            hostname, pid, locktime = file_lock.get_lock_info()

            assert hostname == "test-hostname"
            assert pid == "12345"
            assert locktime == "1000.5"

    def test_get_lock_info_handles_value_error(self):
        """Test get_lock_info handles ValueError."""
        with patch('app.file_lock.get_config') as mock_get_config, \
             patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.read_text', return_value="invalid,format"):
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_config.return_value = mock_config

            file_lock = FileLock()
            hostname, pid, locktime = file_lock.get_lock_info()

            assert hostname is None
            assert pid is None
            assert locktime is None

    def test_get_lock_info_handles_file_not_found_error(self):
        """Test get_lock_info handles FileNotFoundError."""
        with patch('app.file_lock.get_config') as mock_get_config, \
             patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.read_text', side_effect=FileNotFoundError()):
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_config.return_value = mock_config

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
        with patch('app.file_lock.get_config') as mock_get_config, \
             patch.object(FileLock, 'is_locked', return_value=False):
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_config.return_value = mock_config

            file_lock = FileLock()
            await file_lock.wait_for_unlock()

            # Should return immediately without sleeping

    @pytest.mark.asyncio
    async def test_wait_for_unlock_waits_when_locked(self):
        """Test wait_for_unlock waits when locked."""
        with patch('app.file_lock.get_config') as mock_get_config, \
             patch.object(FileLock, 'is_locked', side_effect=[True, True, False]), \
             patch('asyncio.sleep') as mock_sleep:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_config.return_value = mock_config

            file_lock = FileLock()
            await file_lock.wait_for_unlock()

            assert mock_sleep.call_count == 2
            mock_sleep.assert_called_with(1)


class TestFileLockUpdate:
    """Test cases for _update method."""

    def test_update_writes_correct_content(self):
        """Test _update writes correct content to lock file."""
        with patch('app.file_lock.get_config') as mock_get_config, \
             patch('app.file_lock.socket.gethostname', return_value='test-host'), \
             patch('app.file_lock.os.getpid', return_value=54321), \
             patch('app.file_lock.time.time', return_value=2000.123), \
             patch('builtins.open', mock_open()) as mock_file:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_config.return_value = mock_config

            file_lock = FileLock()
            file_lock._update()

            mock_file.assert_called_once_with(file_lock.lock_path, "w")
            mock_file().write.assert_called_once_with("test-host,54321,2000.123")

    def test_update_handles_oserror(self):
        """Test _update handles OSError."""
        with patch('app.file_lock.get_config') as mock_get_config, \
             patch('app.file_lock.socket.gethostname', return_value='test-host'), \
             patch('app.file_lock.os.getpid', return_value=12345), \
             patch('app.file_lock.time.time', return_value=1000.0), \
             patch('builtins.open', side_effect=OSError("Permission denied")), \
             patch('app.file_lock.logger') as mock_logger:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_config.return_value = mock_config

            file_lock = FileLock()
            file_lock._update()

            mock_logger.debug.assert_called_once()
            assert "Error writing lock file" in str(mock_logger.debug.call_args)

    def test_update_handles_ioerror(self):
        """Test _update handles IOError."""
        with patch('app.file_lock.get_config') as mock_get_config, \
             patch('app.file_lock.socket.gethostname', return_value='test-host'), \
             patch('app.file_lock.os.getpid', return_value=12345), \
             patch('app.file_lock.time.time', return_value=1000.0), \
             patch('builtins.open', side_effect=IOError("Disk full")), \
             patch('app.file_lock.logger') as mock_logger:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_config.return_value = mock_config

            file_lock = FileLock()
            file_lock._update()

            mock_logger.debug.assert_called_once()


class TestFileLockHeartbeat:
    """Test cases for _heartbeat method."""

    @pytest.mark.asyncio
    async def test_heartbeat_updates_while_active(self):
        """Test _heartbeat updates lock file while active."""
        with patch('app.file_lock.get_config') as mock_get_config, \
             patch.object(FileLock, '_update') as mock_update, \
             patch('app.file_lock.asyncio.sleep') as mock_sleep:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_config.return_value = mock_config

            file_lock = FileLock()
            file_lock._active = True

            # Make sleep stop the loop after first iteration
            call_count = 0
            async def mock_sleep_side_effect(delay):
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
        with patch('app.file_lock.get_config') as mock_get_config, \
             patch.object(FileLock, '_update') as mock_update, \
             patch('app.file_lock.asyncio.sleep') as mock_sleep:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_config.return_value = mock_config

            file_lock = FileLock()
            file_lock._active = False

            # Start heartbeat task - should exit immediately since _active is False
            task = asyncio.create_task(file_lock._heartbeat())
            
            try:
                await task
            except asyncio.CancelledError:
                pass

            # Update should not be called if _active is False from start
            # The loop should exit immediately without calling _update
            assert not mock_update.called

    @pytest.mark.asyncio
    async def test_heartbeat_sleeps_correct_interval(self):
        """Test _heartbeat sleeps for HEARTBEAT_SEC seconds."""
        with patch('app.file_lock.get_config') as mock_get_config, \
             patch.object(FileLock, '_update') as mock_update, \
             patch('app.file_lock.asyncio.sleep') as mock_sleep:
            
            mock_config = Mock()
            mock_config.data_path = "/test/data"
            mock_get_config.return_value = mock_config

            file_lock = FileLock()
            file_lock._active = True

            # Make sleep stop the loop after first iteration
            call_count = 0
            async def mock_sleep_side_effect(delay):
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


class TestFileLockConstants:
    """Test cases for FileLock constants."""

    def test_heartbeat_sec_constant(self):
        """Test HEARTBEAT_SEC constant value."""
        assert FileLock.HEARTBEAT_SEC == 6

    def test_stale_sec_constant(self):
        """Test STALE_SEC constant value."""
        assert FileLock.STALE_SEC == 10

