"""Loss of shared ownership must stop work before the standby promotes."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI, WebSocketDisconnect
from fastapi.testclient import TestClient
import pytest

from app.lifespan import _maintain_primary
from app.middleware import StandbyMiddleware, is_standby_mode
from app.queue.manager import AsyncQueueManager
from app.routes import create_router


def test_expired_owner_blocks_requests_before_supervisor_runs():
    app = FastAPI()
    app.state.is_standby = False
    app.state.file_lock = Mock(check_owned=Mock(return_value=False))
    app.add_middleware(StandbyMiddleware)

    @app.post('/work')
    def work():
        pytest.fail('Former primary accepted work')

    @app.get('/livez')
    def livez():
        return 'OK'

    assert is_standby_mode(app.state)
    with TestClient(app) as client:
        assert client.post('/work').status_code == 503
        assert client.get('/livez').status_code == 200


@pytest.mark.asyncio
async def test_ownership_loss_cancels_primary_work_and_releases_after_cleanup():
    app = FastAPI()
    shutdown = asyncio.Event()
    pending = asyncio.create_task(asyncio.Event().wait())
    app.state.is_standby = False
    app.state.runtime_tasks = {pending}
    queue_manager = Mock(stop_processing=AsyncMock())
    app.state.queue_manager = queue_manager
    messenger = SimpleNamespace(close=AsyncMock(), chains={}, _async_tasks=set(),
                                _user_scheduler=None, task_management_integration=None)
    app.state.messenger = messenger

    async def released():
        assert pending.cancelled()
        queue_manager.stop_processing.assert_awaited_once_with(cancel=True)
        messenger.close.assert_awaited_once()
        shutdown.set()

    lock = Mock(check_owned=Mock(return_value=False), release_lock=AsyncMock(side_effect=released))
    with patch('app.lifespan.STATUS') as status:
        await asyncio.wait_for(_maintain_primary(shutdown, lock, app), timeout=2)
    assert app.state.is_standby
    assert app.state.queue_manager is None
    status.set.assert_called_with(0)


@pytest.mark.asyncio
async def test_force_stop_cancels_inflight_queue_handler():
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def handler():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    manager = AsyncQueueManager.__new__(AsyncQueueManager)
    manager._running = True
    manager._task = asyncio.create_task(handler())
    await started.wait()
    await asyncio.wait_for(manager.stop_processing(cancel=True), timeout=1)
    assert stopped.is_set()
    assert manager._task is None


@pytest.mark.asyncio
async def test_expired_owner_does_not_dequeue_work():
    manager = AsyncQueueManager.__new__(AsyncQueueManager)
    manager.check_owned = lambda: False
    manager.queue = Mock(get_next_ready_item=AsyncMock())
    await manager.queue_handle_once()
    manager.queue.get_next_ready_item.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('supervisor_demoted', [False, True])
async def test_websocket_save_does_not_start_work_after_ownership_loss(supervisor_demoted):
    app = FastAPI()
    owned = True
    app.state.is_standby = False
    app.state.file_lock = SimpleNamespace(check_owned=lambda: owned)
    app.state.runtime_tasks = set()
    app.state.messenger = SimpleNamespace(users=SimpleNamespace(get_assignable_users=lambda: []))
    effects = AsyncMock()
    app.state.maintenance_manager = SimpleNamespace(
        active_windows_payload=lambda: [], apply_save_side_effects=effects,
    )

    class Socket:
        def __init__(self):
            self.app = app
            self.received = False

        async def receive_text(self):
            if self.received:
                raise WebSocketDisconnect()
            self.received = True
            return json.dumps({'event': 'save_maintenance', 'data': []})

        async def send_text(self, data):
            nonlocal owned
            if json.loads(data)['event'] == 'maintenance_saved':
                # Renewal can fail while the acknowledgement is being sent.
                owned = False
                app.state.is_standby = supervisor_demoted
                if supervisor_demoted:
                    for task in list(app.state.runtime_tasks):
                        task.cancel()
                await asyncio.sleep(0)

        async def close(self, **kwargs):
            pass

    store = Mock(load_windows=Mock(return_value=[]), save_windows=Mock(return_value=True))
    with patch('app.routes.get_maintenance_store', return_value=store), \
            patch('app.routes.incident_ws.connect', new=AsyncMock()), \
            patch('app.routes.incident_ws.disconnect'):
        endpoint = next(route.endpoint for route in create_router('').routes if route.path == '/ws')
        task = asyncio.create_task(endpoint(Socket()))
        result, = await asyncio.gather(task, return_exceptions=True)
        if supervisor_demoted:
            assert isinstance(result, asyncio.CancelledError)
        else:
            assert result is None
        await asyncio.sleep(0)
    effects.assert_not_awaited()
    assert not app.state.runtime_tasks
