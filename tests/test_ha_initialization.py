"""Primary initialization must stop when its acquired lease is lost."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI
import pytest

from app.lifespan import _initialize_primary_server


@pytest.mark.asyncio
async def test_ownership_loss_cancels_initialization_before_further_work():
    app = FastAPI()
    lost = asyncio.Event()
    started = asyncio.Event()
    cancelled = asyncio.Event()
    future_side_effect = Mock()

    async def initialize(_app):
        started.set()
        try:
            await asyncio.Event().wait()
            future_side_effect()
        finally:
            cancelled.set()

    async def release():
        assert cancelled.is_set()

    lock = SimpleNamespace(
        acquire_lock=lambda: True,
        check_owned=lambda: not lost.is_set(),
        release_lock=AsyncMock(side_effect=release),
    )
    with patch('app.lifespan.create_main_objects', side_effect=initialize), \
            patch('app.lifespan._cleanup_application_objects', new=AsyncMock()) as cleanup, \
            patch('app.lifespan.STATUS') as status:
        initialization = asyncio.create_task(_initialize_primary_server(app, lock))
        try:
            await asyncio.wait_for(started.wait(), timeout=1)
            lost.set()
            assert await asyncio.wait_for(initialization, timeout=1) is False
        finally:
            if not initialization.done():
                initialization.cancel()
                await asyncio.gather(initialization, return_exceptions=True)

    assert cancelled.is_set()
    future_side_effect.assert_not_called()
    cleanup.assert_awaited_once_with(app, cancel=True)
    lock.release_lock.assert_awaited_once()
    assert app.state.is_standby
    status.set.assert_called_with(0)
