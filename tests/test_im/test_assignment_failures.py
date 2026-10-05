import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.im.application import Application
from app.im.interactions import toggle_assignment
from app.im.users import ProfileUser, UserManager
from app.routes import create_router
from impulse_messenger_api import ProviderDescriptor, UserProfile


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ['ui', 'callback'])
@pytest.mark.parametrize('failure', ['missing', 'timeout'])
async def test_failed_assignment_preserves_escalation(action, failure):
    app = Application.__new__(Application)
    app.provider = SimpleNamespace(fetch_user=AsyncMock(
        return_value=UserProfile('missing', False),
        side_effect=asyncio.TimeoutError if failure == 'timeout' else None,
    ))
    app.users = UserManager()
    app._async_tasks = set()
    app.post_assignment_notification = AsyncMock()
    app.update_incident_message = AsyncMock()
    incident = SimpleNamespace(uniq_id='incident-1', assigned_user_id='', assigned_user='',
                               assigned_fullname='', chain_enabled=True, status='firing', dump=Mock())
    queue = SimpleNamespace(delete_by_id=AsyncMock())

    if action == 'ui':
        assert await app.handle_ui_assignment(incident, 'missing', queue) is False
    else:
        await toggle_assignment(app, incident, 'missing', queue)

    assert incident.assigned_user_id == '' and incident.chain_enabled
    queue.delete_by_id.assert_not_awaited()
    app.post_assignment_notification.assert_not_awaited()
    app.update_incident_message.assert_not_awaited()
    incident.dump.assert_not_called()
    assert not app._async_tasks


@pytest.mark.asyncio
async def test_cached_assignment_returns_success_and_stops_escalation():
    app = Application.__new__(Application)
    app.users = UserManager()
    app.users.add_user('123', ProfileUser('Alice', id_='123', exists=True, username='alice'))
    app._async_tasks = set()
    app.post_assignment_notification = AsyncMock()
    app.update_incident_message = AsyncMock()
    incident = SimpleNamespace(uniq_id='incident-1', assigned_user_id='', chain_enabled=True, dump=Mock())
    queue = SimpleNamespace(delete_by_id=AsyncMock())

    assert await app.handle_ui_assignment(incident, 123, queue) is True
    await asyncio.gather(*app._async_tasks)
    assert incident.assigned_user_id == '123' and not incident.chain_enabled
    queue.delete_by_id.assert_awaited_once()
    app.post_assignment_notification.assert_awaited_once()


@pytest.mark.parametrize('already_assigned, expected_status', [(False, 502), (True, 200)])
def test_assignment_api_does_not_report_failed_lookup_as_http_success(already_assigned, expected_status):
    incident = SimpleNamespace(uniq_id='incident-1', assigned_user_id=123 if already_assigned else '')
    app = FastAPI()
    app.state.incidents = Mock(get_by_uniq_id=Mock(return_value=incident))
    app.state.messenger = Mock(handle_ui_assignment=AsyncMock(return_value=False))
    app.state.queue = Mock()
    app.include_router(create_router(''))
    response = TestClient(app).post('/assign', json={'uniq_id': 'incident-1', 'user_id': '123'})
    assert response.status_code == expected_status


@pytest.mark.asyncio
async def test_failed_freeze_actor_lookup_preserves_escalation(monkeypatch):
    app = Application.__new__(Application)
    app.provider = SimpleNamespace(descriptor=ProviderDescriptor('test'))
    app.fetch_and_assign_user_name = AsyncMock(return_value=False)
    app.users = UserManager()
    app.apply_time_freeze = AsyncMock()
    app.post_freeze_notification = AsyncMock()
    app.update_incident_message = AsyncMock()
    incident = SimpleNamespace(uniq_id='incident-1')
    monkeypatch.setattr('app.im.application.calculate_freeze_time', Mock())

    assert await app.handle_ui_freeze(incident, 'tomorrow', 'missing', Mock()) is False
    app.apply_time_freeze.assert_not_awaited()
    app.update_incident_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_anonymous_ui_freeze_remains_available(monkeypatch):
    app = Application.__new__(Application)
    app.provider = SimpleNamespace(descriptor=ProviderDescriptor('test'))
    app.fetch_and_assign_user_name = AsyncMock()
    app.users = UserManager()
    app.apply_time_freeze = AsyncMock()
    app.post_freeze_notification = AsyncMock()
    app.update_incident_message = AsyncMock()
    monkeypatch.setattr('app.im.application.calculate_freeze_time', Mock())

    assert await app.handle_ui_freeze(SimpleNamespace(uniq_id='incident-1'), 'tomorrow', '', Mock()) is True
    app.fetch_and_assign_user_name.assert_not_awaited()
    assert app.apply_time_freeze.await_args.args[2] is None


def test_freeze_api_returns_http_failure_when_action_fails():
    app = FastAPI()
    app.state.incidents = Mock(get_by_uniq_id=Mock(return_value=SimpleNamespace(uniq_id='incident-1', is_frozen=False)))
    app.state.messenger = Mock(handle_ui_freeze=AsyncMock(return_value=False))
    app.state.queue = Mock()
    app.include_router(create_router(''))
    response = TestClient(app).post('/freeze', json={'uniq_id': 'incident-1', 'freeze_option': 'tomorrow'})
    assert response.status_code == 502
