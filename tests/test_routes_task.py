"""POST /task must report task creation failures (#670)."""
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.incident.incidents import Incidents
from app.routes import create_router


def _app(incident, task_result):
    messenger = Mock()
    messenger.handle_task_button = AsyncMock(return_value=task_result)
    app = FastAPI()
    app.state.messenger = messenger
    app.state.incidents = Incidents([incident])
    app.state.queue = AsyncMock()
    app.include_router(create_router(''))
    return app


async def _post_task(app, uniq_id):
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        return await client.post('/task', json={'uniq_id': uniq_id})


@pytest.mark.asyncio
@pytest.mark.parametrize('task_result, message', [
    ({'success': False, 'message': 'Failed to create Jira task'}, 'Failed to create Jira task'),
    ({'success': False, 'message': 'Task management integration not available'},
     'Task management integration not available'),
    ({'success': False}, 'Could not create the task'),
])
async def test_post_task_returns_502_when_creation_fails(sample_incident, task_result, message):
    response = await _post_task(_app(sample_incident, task_result), sample_incident.uniq_id)

    assert response.status_code == 502
    assert response.json() == {'detail': message}


@pytest.mark.asyncio
async def test_post_task_returns_result_when_task_is_created(sample_incident):
    task_result = {'success': True, 'message': 'Created Jira task: KAN-1', 'task_key': 'KAN-1',
                   'task_url': 'https://jira.example.com/browse/KAN-1'}

    response = await _post_task(_app(sample_incident, task_result), sample_incident.uniq_id)

    assert response.status_code == 200
    assert response.json() == {'success': True, 'result': task_result}
