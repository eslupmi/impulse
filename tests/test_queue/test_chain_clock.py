"""Chain step delays must keep counting across IMPulse restarts (#669)."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.queue.constants import QueueItemType
from app.queue.queue import AsyncQueue


def _remaining_seconds(queue, uniq_id):
    steps = [item for item in queue.items if item.uniq_id == uniq_id and item.type == QueueItemType.CHAIN_STEP]
    return [(item.datetime - datetime.now(UTC)).total_seconds() for item in steps]


@pytest.fixture
def incident(sample_incident, monkeypatch):
    monkeypatch.setattr(sample_incident, 'dump', Mock())
    sample_incident.status = 'firing'
    sample_incident.chain_enabled = True
    sample_incident.chain_put(0, 0.0, 'user', 'alice')
    sample_incident.chain_update(0, done=True, result=200)
    sample_incident.chain_put(1, 180.0, 'user', 'alice')
    return sample_incident


async def _recreate(incident):
    return await AsyncQueue.recreate_queue(SimpleNamespace(uniq_ids={incident.uniq_id: incident}))


@pytest.mark.asyncio
async def test_restart_counts_from_last_status_change(incident):
    incident.updated = datetime.now(UTC) - timedelta(seconds=60)

    queue = await _recreate(incident)

    assert _remaining_seconds(queue, incident.uniq_id) == [pytest.approx(120, abs=2)]
    assert incident.chain_active_seconds == 0.0


@pytest.mark.asyncio
async def test_restart_adds_time_accumulated_before_resolve(incident):
    incident.chain_active_seconds = 100.0
    incident.updated = datetime.now(UTC) - timedelta(seconds=20)

    queue = await _recreate(incident)

    assert _remaining_seconds(queue, incident.uniq_id) == [pytest.approx(60, abs=2)]


@pytest.mark.asyncio
async def test_overdue_step_runs_immediately(incident):
    incident.updated = datetime.now(UTC) - timedelta(seconds=600)

    queue = await _recreate(incident)

    assert _remaining_seconds(queue, incident.uniq_id) == [pytest.approx(0, abs=2)]
