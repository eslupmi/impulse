import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.im.application import Application
from app.im.interactions import apply_interaction
from app.im.users import ProfileUser, UserManager
from app.incident.incidents import Incidents
from app.queue.constants import QueueItemType
from app.queue.handlers.alert_handler import AlertHandler
from app.queue.queue import AsyncQueue
from app.routes import create_router
from impulse_messenger_api import (
    Interaction, InteractionAction, InteractionCommand, MessageRef, ProviderDescriptor, ProviderResponse,
)
from tests.utils import create_alert_payload


@pytest.mark.asyncio
@pytest.mark.parametrize('action, status, chain_enabled, assigns', [
    (InteractionAction.ASSIGN, 'resolved', False, True),
    (InteractionAction.RELEASE, 'firing', True, False),
    (InteractionAction.TOGGLE_ASSIGNMENT, 'resolved', False, False),
    (InteractionAction.TOGGLE_ASSIGNMENT, 'firing', True, True),
])
async def test_assignment_commands_preserve_explicit_intent(action, status, chain_enabled, assigns):
    app = Application.__new__(Application)
    app.provider = SimpleNamespace(descriptor=ProviderDescriptor('test'), respond_to_interaction=Mock(return_value=ProviderResponse()))
    app.users = UserManager()
    app.users.add_user('123', ProfileUser('Alice', id_='123', exists=True))
    app._async_tasks = set()
    app._get_user_timezone_str = Mock(return_value='UTC')
    app.post_assignment_notification = AsyncMock()
    app.post_unassignment_notification = AsyncMock()
    app.form_body_header_status_icons = Mock(return_value=('', '', ''))
    app._presentation = Mock()
    incident = SimpleNamespace(uniq_id='incident-1', channel_id='C1', status=status, chain_enabled=chain_enabled,
                               assigned_user_id='456', is_frozen=False, dump=Mock(), release=Mock())
    queue = SimpleNamespace(delete_by_id=AsyncMock())
    interaction = Interaction(MessageRef('C1', 'thread-1'), 123, (InteractionCommand(action),))

    await apply_interaction(app, interaction, Mock(get_by_ts=Mock(return_value=incident)), queue)
    await asyncio.gather(*app._async_tasks)
    assert incident.release.called is not assigns
    if assigns:
        assert incident.assigned_user_id == 123
        assert not incident.chain_enabled
        app.post_assignment_notification.assert_awaited_once_with(incident)
    else:
        app.post_unassignment_notification.assert_awaited_once_with(incident)
    queue.delete_by_id.assert_awaited_once()


@pytest.mark.asyncio
async def test_ui_unassign_resolved_incident_restarts_chain_on_refiring(sample_incident, mock_unified_config, monkeypatch):
    incident = sample_incident
    monkeypatch.setattr(incident, 'dump', Mock())
    monkeypatch.setattr('app.incident.incident.get_config', lambda: mock_unified_config)
    monkeypatch.setattr('app.queue.handlers.alert_handler.get_config', lambda: mock_unified_config)
    incident.status = 'resolved'
    incident.assigned_user_id = '123'
    incident.chain_put(0, 0.0, 'user', 'alice')
    incident.chain_update(0, done=True, result=200)
    incident.chain_active_seconds = 30.0

    messenger = Application.__new__(Application)
    messenger._async_tasks = set()
    messenger.post_unassignment_notification = AsyncMock()
    messenger.update_incident_message = AsyncMock()
    messenger.update = AsyncMock()
    messenger.chains = {'oncall': SimpleNamespace(steps=[{'user': 'alice'}])}
    queue = AsyncQueue()
    incidents = Incidents([incident])
    app = FastAPI()
    app.state.messenger = messenger
    app.state.queue = queue
    app.state.incidents = incidents
    app.include_router(create_router(''))

    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post('/assign', json={'uniq_id': incident.uniq_id, 'user_id': ''})
    await asyncio.gather(*messenger._async_tasks)
    assert response.json() == {'success': True}
    assert incident.assigned_user_id == ''
    assert incident.chain_steps == []
    assert incident.chain_active_seconds == 0.0
    assert not queue.items
    messenger.post_unassignment_notification.assert_awaited_once()

    alerts = AlertHandler(
        queue, messenger, incidents, Mock(get_route=Mock(return_value=('default', 'oncall'))),
        SimpleNamespace(process_incident=AsyncMock()), SimpleNamespace(process_incident=AsyncMock()),
    )
    await alerts.handle(create_alert_payload(status='firing'))

    assert (await queue.get_next_ready_item())[:3] == (QueueItemType.CHAIN_STEP, incident.uniq_id, 0)
    assert incident.chain_steps[0]['value'] == 'alice'
    assert not incident.chain_steps[0]['done']


@pytest.mark.asyncio
@pytest.mark.parametrize('status', ['firing', 'unknown'])
async def test_ui_unassign_preserves_active_chain_progress(status, sample_incident, monkeypatch):
    incident = sample_incident
    monkeypatch.setattr(incident, 'dump', Mock())
    incident.status = status
    incident.assigned_user_id = '123'
    incident.chain_put(0, 0.0, 'user', 'alice')
    incident.chain_update(0, done=True, result=200)
    incident.chain_put(1, 300.0, 'user', 'bob')
    incident.chain_active_seconds = 30.0
    original_steps = [step.copy() for step in incident.chain_steps]

    messenger = Application.__new__(Application)
    messenger._async_tasks = set()
    messenger.post_unassignment_notification = AsyncMock()
    messenger.update_incident_message = AsyncMock()

    unassigned = await messenger.handle_ui_unassign(incident, AsyncQueue())
    await asyncio.gather(*messenger._async_tasks)

    assert unassigned is True
    assert incident.assigned_user_id == ''
    assert incident.get_chain() == original_steps
    assert incident.chain_active_seconds == 30.0
