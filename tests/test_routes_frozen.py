"""UI/API actions that the messenger ignores for frozen incidents are rejected (#672)."""
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.incident.incidents import Incidents
from app.routes import create_router


def _freeze(incident, source):
    if source == 'inhibition':
        incident.parents = ['source-uniq-id']
    else:
        incident.frozen_until = datetime.now(UTC) + timedelta(days=1)
        incident.frozen_until_source = 'time'


def _app(incident):
    messenger = Mock()
    messenger.handle_ui_assignment = AsyncMock(return_value=True)
    messenger.handle_ui_unassign = AsyncMock(return_value=True)
    messenger.handle_task_button = AsyncMock(return_value={'success': True})
    app = FastAPI()
    app.state.messenger = messenger
    app.state.incidents = Incidents([incident])
    app.state.queue = AsyncMock()
    app.include_router(create_router(''))
    return app, messenger


async def _post(app, path, body):
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        return await client.post(path, json=body)


@pytest.mark.asyncio
@pytest.mark.parametrize('source', ['inhibition', 'time'])
@pytest.mark.parametrize('user_id', ['U123', ''])
async def test_assign_rejects_frozen_incident(sample_incident, source, user_id):
    _freeze(sample_incident, source)
    app, messenger = _app(sample_incident)

    response = await _post(app, '/assign', {'uniq_id': sample_incident.uniq_id, 'user_id': user_id})

    assert response.status_code == 409
    assert response.json() == {'detail': 'Incident is frozen'}
    messenger.handle_ui_assignment.assert_not_called()
    messenger.handle_ui_unassign.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('source', ['inhibition', 'time'])
async def test_task_rejects_frozen_incident(sample_incident, source):
    _freeze(sample_incident, source)
    app, messenger = _app(sample_incident)

    response = await _post(app, '/task', {'uniq_id': sample_incident.uniq_id})

    assert response.status_code == 409
    assert response.json() == {'detail': 'Incident is frozen'}
    messenger.handle_task_button.assert_not_called()


@pytest.mark.asyncio
async def test_assign_and_task_work_for_active_incident(sample_incident):
    app, messenger = _app(sample_incident)

    assign = await _post(app, '/assign', {'uniq_id': sample_incident.uniq_id, 'user_id': 'U123'})
    task = await _post(app, '/task', {'uniq_id': sample_incident.uniq_id})

    assert assign.status_code == 200
    assert task.status_code == 200
    messenger.handle_ui_assignment.assert_awaited_once()
    messenger.handle_task_button.assert_awaited_once()
