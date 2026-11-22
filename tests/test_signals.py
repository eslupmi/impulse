import asyncio
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI
import pytest

from app.file_lock import FileLock
from app.s3_lock import S3Lock
from app.signals import setup_sighup_handler


@pytest.mark.asyncio
@pytest.mark.parametrize('reload_ok,owned_before,owned_after', [
    (True, True, True),
    (False, True, True),
    (True, False, False),
    (True, True, False),
])
async def test_sighup_reload_tracks_work_and_requires_ownership(reload_ok, owned_before, owned_after, monkeypatch):
    monkeypatch.setattr('app.signals.signal.SIGHUP', 1, raising=False)
    app = FastAPI()
    owned = owned_before
    app.state.is_standby = False
    app.state.file_lock = Mock(spec=S3Lock, check_owned=lambda: owned)
    app.state.runtime_tasks = set()
    cleanup, create = AsyncMock(), AsyncMock()

    with patch('app.signals.reload_config', return_value=reload_ok), \
            patch('app.signals.signal.signal') as registered:
        setup_sighup_handler(app, create, cleanup)
        handler = registered.call_args.args[1]
        handler(1, None)
        pending = tuple(app.state.runtime_tasks)
        assert bool(pending) == (reload_ok and owned_before)
        owned = owned_after
        await asyncio.gather(*pending)
        await asyncio.sleep(0)

    if reload_ok and owned_before and owned_after:
        cleanup.assert_awaited_once_with(app, reload=True)
        create.assert_awaited_once_with(app, reload=True)
    else:
        cleanup.assert_not_awaited()
        create.assert_not_awaited()
    assert not app.state.runtime_tasks


@pytest.mark.asyncio
@pytest.mark.parametrize('standby', [False, True])
async def test_filesystem_sighup_uses_standby_state_without_lease_checks(standby, monkeypatch):
    monkeypatch.setattr('app.signals.signal.SIGHUP', 1, raising=False)
    app = FastAPI()
    app.state.is_standby = standby
    app.state.file_lock = Mock(spec=FileLock)
    app.state.runtime_tasks = set()
    cleanup, create = AsyncMock(), AsyncMock()

    with patch('app.signals.reload_config', return_value=True), \
            patch('app.signals.signal.signal') as registered:
        setup_sighup_handler(app, create, cleanup)
        registered.call_args.args[1](1, None)
        await asyncio.gather(*app.state.runtime_tasks)
        await asyncio.sleep(0)

    if standby:
        cleanup.assert_not_awaited()
        create.assert_not_awaited()
    else:
        cleanup.assert_awaited_once_with(app, reload=True)
        create.assert_awaited_once_with(app, reload=True)
    assert not app.state.runtime_tasks
