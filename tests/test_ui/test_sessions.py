import asyncio
import threading
from datetime import UTC, datetime, timedelta
from errno import EACCES
from unittest.mock import Mock, patch

import pytest

from app.logging import JSONFormatter
from app.storage import FileStorage
from app.ui.authentication import cleanup_sessions
from app.ui.authentication.models.auth_session import AuthSession
from app.ui.authentication.session_store import FileSessionStore


async def wait_until(predicate):
    async with asyncio.timeout(2):
        while not predicate():
            await asyncio.sleep(0.001)


@pytest.mark.asyncio
async def test_background_cleanup_removes_abandoned_sessions_without_requests(tmp_path, monkeypatch):
    store = FileSessionStore(str(tmp_path), storage=FileStorage())
    now = datetime.now(UTC)
    expired = AuthSession(session_id='a' * 64, user_id='U1', created_at=now - timedelta(days=91),
                          expires_at=now - timedelta(days=1))
    active = expired.model_copy(update={'session_id': 'b' * 64, 'expires_at': now + timedelta(days=1)})
    store.save_session(expired)
    store.save_session(active)
    malformed = tmp_path / 'malformed.yaml'
    malformed.write_text('not: [valid yaml', encoding='utf-8')
    invalid_utf8 = tmp_path / f'{"c" * 64}.yaml'
    invalid_utf8.write_bytes(b'\xff')
    invalid_timestamp = tmp_path / f'{"e" * 64}.yaml'
    invalid_timestamp.write_text('expires_at: 2026-99-99', encoding='utf-8')
    unrelated = tmp_path / 'notes.txt'
    unrelated.write_text('keep', encoding='utf-8')
    monkeypatch.setattr(cleanup_sessions, 'SESSION_CLEANUP_INTERVAL_SECONDS', 0.01)
    task = asyncio.create_task(cleanup_sessions.run_session_cleanup(store))
    try:
        await wait_until(lambda: not (tmp_path / f'{expired.session_id}.yaml').exists())
        second = expired.model_copy(update={'session_id': 'd' * 64})
        store.save_session(second)
        await wait_until(lambda: not (tmp_path / f'{second.session_id}.yaml').exists())
        assert store.load_session(active.session_id) == active
        assert store.load_session('c' * 64) is None
        assert store.load_session('e' * 64) is None
        assert malformed.read_text(encoding='utf-8') == 'not: [valid yaml'
        assert invalid_utf8.read_bytes() == b'\xff'
        assert invalid_timestamp.read_text(encoding='utf-8') == 'expires_at: 2026-99-99'
        assert unrelated.read_text(encoding='utf-8') == 'keep'
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_background_cleanup_retries_storage_failure(monkeypatch, caplog):
    store = Mock(spec=FileSessionStore)

    def cleanup():
        if store.cleanup_expired.call_count == 1:
            raise OSError('storage unavailable')
        return 0

    store.cleanup_expired.side_effect = cleanup
    monkeypatch.setattr(cleanup_sessions, 'SESSION_CLEANUP_INTERVAL_SECONDS', 0.01)
    task = asyncio.create_task(cleanup_sessions.run_session_cleanup(store))
    try:
        await wait_until(lambda: store.cleanup_expired.call_count >= 2)
        assert not task.done()
        assert 'Failed to clean up expired auth sessions' in caplog.text
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
@pytest.mark.parametrize('fail', [False, True])
async def test_cleanup_cancellation_waits_for_running_scan_without_blocking_event_loop(fail):
    loop = asyncio.get_running_loop()
    entered = asyncio.Event()
    release = threading.Event()
    finished = threading.Event()

    def cleanup():
        loop.call_soon_threadsafe(entered.set)
        release.wait(timeout=2)
        finished.set()
        if fail:
            raise OSError('storage failed during shutdown')
        return 0

    store = Mock(spec=FileSessionStore)
    store.cleanup_expired.side_effect = cleanup
    task = asyncio.create_task(cleanup_sessions.run_session_cleanup(store))
    try:
        await asyncio.wait_for(entered.wait(), timeout=1)
        assert not finished.is_set()
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        assert not finished.is_set()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=1)
        assert finished.is_set()
    finally:
        release.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def test_missing_session_directory_needs_no_cleanup(tmp_path):
    store = FileSessionStore(str(tmp_path / 'sessions'), storage=FileStorage())
    assert store.cleanup_expired() == 0
    assert not store.root_dir.exists()


def test_session_read_failure_does_not_log_cookie(tmp_path, monkeypatch, caplog):
    storage = FileStorage()
    store = FileSessionStore(str(tmp_path), storage=storage)
    now = datetime.now(UTC)
    session = AuthSession(session_id='a' * 64, user_id='U1', created_at=now, expires_at=now + timedelta(days=1))
    store.save_session(session)

    with monkeypatch.context() as denied:
        denied.setattr(storage, 'open', Mock(side_effect=PermissionError(
            EACCES, 'Permission denied', str(tmp_path / f'{session.session_id}.yaml'),
        )))
        assert store.cleanup_expired() == 0
        assert store.load_session(session.session_id) is None

    assert store.load_session(session.session_id) == session
    assert caplog.records
    formatter = JSONFormatter()
    assert all(session.session_id not in formatter.format(record) for record in caplog.records)


def test_cleanup_skips_malformed_yaml_timestamp(tmp_path, monkeypatch):
    storage = FileStorage()
    store = FileSessionStore(str(tmp_path), storage=storage)
    now = datetime.now(UTC)
    malformed = tmp_path / f'{"a" * 64}.yaml'
    malformed.write_text('expires_at: !!timestamp invalid', encoding='utf-8')
    expired = AuthSession(session_id='b' * 64, user_id='U1', created_at=now, expires_at=now - timedelta(days=1))
    store.save_session(expired)
    expired_path = tmp_path / f'{expired.session_id}.yaml'
    monkeypatch.setattr(storage, 'listdir', Mock(return_value=[malformed.name, expired_path.name]))

    assert store.cleanup_expired() == 1
    assert not expired_path.exists()
    assert malformed.exists()
    assert store.load_session(malformed.stem) is None


@pytest.mark.parametrize('naive', [False, True])
def test_cleanup_expiry_boundary_uses_utc(tmp_path, naive):
    store = FileSessionStore(str(tmp_path), storage=FileStorage())
    now = datetime(2026, 11, 15, tzinfo=UTC)
    expires_at = now.replace(tzinfo=None) if naive else now
    session = AuthSession(session_id='a' * 64, user_id='U1', created_at=now - timedelta(days=90),
                          expires_at=expires_at)
    store.save_session(session)
    with patch('app.ui.authentication.session_store.datetime', wraps=datetime) as clock:
        clock.now.return_value = now
        assert store.cleanup_expired() == 1
    assert not (tmp_path / f'{session.session_id}.yaml').exists()
