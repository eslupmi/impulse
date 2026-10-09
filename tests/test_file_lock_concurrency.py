import asyncio
import errno
import multiprocessing
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from app.file_lock import FileLock


def _make_lock(root):
    with patch('app.file_lock.get_environment_config', return_value=SimpleNamespace(data_path=str(root))):
        return FileLock()


def _contender(root, results, finish, paused=None, resume=None, pause_at='mkdir'):
    lock = _make_lock(root)
    original_mkdir = Path.mkdir
    import shutil
    original_rmtree = shutil.rmtree

    def wait_if_selected(path):
        if Path(path) == lock.lock_dir and not paused.is_set():
            paused.set()
            if not resume.wait(10):
                raise TimeoutError('publisher was not resumed')

    def paused_mkdir(path, *args, **kwargs):
        result = original_mkdir(path, *args, **kwargs)
        wait_if_selected(path)
        return result

    def paused_cleanup(path, *args, **kwargs):
        wait_if_selected(path)
        return original_rmtree(path, *args, **kwargs)

    if paused is None:
        acquired = lock.acquire_lock()
    elif pause_at == 'mkdir':
        with patch.object(Path, 'mkdir', paused_mkdir):
            acquired = lock.acquire_lock()
    else:
        with patch('app.file_lock.shutil.rmtree', paused_cleanup):
            acquired = lock.acquire_lock()
    results.put(acquired)
    finish.wait(10)
    if acquired:
        asyncio.run(lock.release_lock())


def _stop(processes, finish, resume):
    resume.set()
    finish.set()
    for process in processes:
        if process.pid is not None:
            process.join(5)
            if process.is_alive():
                process.terminate()
                process.join(5)


def _publication_race(root, pause_at):
    context = multiprocessing.get_context('spawn')
    results = context.Queue()
    finish, paused, resume = context.Event(), context.Event(), context.Event()
    first = context.Process(target=_contender, args=(root, results, finish, paused, resume, pause_at))
    second = context.Process(target=_contender, args=(root, results, finish))
    try:
        first.start()
        assert paused.wait(10), 'first instance did not reach the controlled race'
        second.start()
        assert results.get(timeout=10) is False
        resume.set()
        assert results.get(timeout=10) is True
    finally:
        _stop((first, second), finish, resume)
        results.close()


def test_contender_cannot_remove_a_directory_before_metadata_is_published(tmp_path):
    _publication_race(tmp_path, 'mkdir')
    assert (tmp_path / '.lock.guard').exists()


@pytest.mark.asyncio
async def test_failed_owner_publication_removes_its_partial_directory(tmp_path):
    import builtins
    lock = _make_lock(tmp_path)
    original_open = builtins.open

    def fail_owner_write(path, *args, **kwargs):
        if Path(path) == lock.owner_path:
            lock.owner_path.write_text('partial-owner')
            raise OSError('Disk full')
        return original_open(path, *args, **kwargs)

    with patch('builtins.open', side_effect=fail_owner_write):
        assert lock.acquire_lock() is False
    assert not lock.lock_dir.exists()
    successor = _make_lock(tmp_path)
    try:
        assert successor.acquire_lock()
    finally:
        await successor.release_lock()


@pytest.mark.asyncio
async def test_stale_cleanup_and_successor_publication_are_one_critical_section(tmp_path):
    old = _make_lock(tmp_path)
    assert old.acquire_lock()
    old.heartbeat_path.write_text(str(time.time() - old.STALE_SEC - 1))
    try:
        _publication_race(tmp_path, 'cleanup')
    finally:
        await old.release_lock()


@pytest.mark.asyncio
async def test_crashed_publisher_releases_the_native_guard(tmp_path):
    context = multiprocessing.get_context('spawn')
    results = context.Queue()
    finish, paused, resume = context.Event(), context.Event(), context.Event()
    process = context.Process(target=_contender, args=(tmp_path, results, finish, paused, resume))
    successor = _make_lock(tmp_path)
    try:
        process.start()
        assert paused.wait(10)
        process.terminate()
        process.join(5)
        assert not process.is_alive()
        assert successor.acquire_lock()
        assert successor.check_owned()
    finally:
        if process.is_alive():
            process.terminate()
            process.join(5)
        await successor.release_lock()
        results.close()


@pytest.mark.asyncio
async def test_old_owner_cannot_renew_or_release_a_same_process_successor(tmp_path):
    first, successor = _make_lock(tmp_path), _make_lock(tmp_path)
    assert first.acquire_lock()
    first_token = first.owner_path.read_text()
    first.heartbeat_path.write_text(str(time.time() - first.STALE_SEC - 1))
    try:
        assert successor.acquire_lock()
        assert successor.owner_path.read_text() != first_token
        heartbeat = successor.heartbeat_path.read_text()
        assert first._update() is False
        assert first.check_owned() is False
        assert successor.heartbeat_path.read_text() == heartbeat
        await first.release_lock()
        assert successor.check_owned()
    finally:
        await successor.release_lock()
        await first.release_lock()


@pytest.mark.asyncio
async def test_expired_local_deadline_fails_closed_and_cannot_be_renewed(tmp_path):
    lock = _make_lock(tmp_path)
    assert lock.acquire_lock()
    heartbeat = lock.heartbeat_path.read_text()
    lock._deadline = time.monotonic() - 1
    try:
        assert lock.check_owned() is False
        assert lock._active is False
        assert lock._update() is False
        assert lock.heartbeat_path.read_text() == heartbeat
        assert lock.acquire_lock() is False
    finally:
        await lock.release_lock()


@pytest.mark.asyncio
async def test_delayed_renewal_cannot_extend_a_lease_that_expired_during_the_write(tmp_path):
    lock = _make_lock(tmp_path)
    assert lock.acquire_lock()
    deadline = lock._deadline
    try:
        with patch('app.file_lock.time.monotonic', side_effect=[deadline - 1, deadline + 1]):
            assert lock._update() is False
        assert lock._active is False
        assert lock._deadline == deadline
    finally:
        await lock.release_lock()


@pytest.mark.asyncio
async def test_busy_guard_does_not_block_or_demote_the_current_owner(tmp_path):
    lock = _make_lock(tmp_path)
    assert lock.acquire_lock()
    try:
        with lock._guard():
            assert lock.check_owned()
            lock.owner_path.write_text('successor-token')
            assert lock.check_owned() is False
    finally:
        await lock.release_lock()


@pytest.mark.asyncio
async def test_windows_guard_contention_preserves_ownership_but_open_denial_does_not(tmp_path):
    lock = _make_lock(tmp_path)
    assert lock.acquire_lock()
    windows_locking = SimpleNamespace(
        locking=Mock(side_effect=OSError(errno.EACCES, 'guard held')),
        LK_LOCK=0, LK_NBLCK=1, LK_UNLCK=2,
    )
    try:
        with patch('app.file_lock.sys.platform', 'win32'), \
                patch('app.file_lock.msvcrt', windows_locking, create=True):
            assert lock.check_owned()
            assert lock._active is True
            assert windows_locking.locking.call_args.args[1] == windows_locking.LK_NBLCK
            windows_locking.locking.reset_mock()
            with patch('app.file_lock.open', side_effect=PermissionError(errno.EACCES, 'open denied'), create=True):
                assert lock.check_owned() is False
                assert lock._active is False
                windows_locking.locking.assert_not_called()
    finally:
        await lock.release_lock()


@pytest.mark.asyncio
async def test_different_pid_namespace_cannot_take_over_a_fresh_lock(tmp_path):
    first, contender = _make_lock(tmp_path), _make_lock(tmp_path)
    assert first.acquire_lock()
    contender._pid_namespace = 'different-namespace'
    try:
        with patch.object(contender, '_is_process_running', return_value=False) as check_process:
            assert contender.can_take_over_lock() is False
            assert contender.acquire_lock() is False
            check_process.assert_not_called()
        first.heartbeat_path.write_text(str(time.time() - first.STALE_SEC - 1))
        assert contender.acquire_lock()
    finally:
        await contender.release_lock()
        await first.release_lock()


@pytest.mark.asyncio
async def test_missing_pid_namespace_uses_heartbeat_expiry(tmp_path):
    first, contender = _make_lock(tmp_path), _make_lock(tmp_path)
    assert first.acquire_lock()
    contender._pid_namespace = None
    try:
        with patch.object(contender, '_is_process_running', return_value=False) as check_process:
            assert contender.can_take_over_lock() is False
            assert contender.acquire_lock() is False
            check_process.assert_not_called()
    finally:
        await first.release_lock()
