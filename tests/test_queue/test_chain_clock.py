"""Chain step delays must keep counting across IMPulse restarts (#669)."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.queue.constants import QueueItemType
from app.queue.queue import AsyncQueue


def _chain_steps(queue, uniq_id):
    return [item for item in queue.items if item.uniq_id == uniq_id and item.type == QueueItemType.CHAIN_STEP]


@pytest.fixture
def incident(sample_incident, monkeypatch):
    monkeypatch.setattr(sample_incident, 'dump', Mock())
    sample_incident.chain_enabled = True
    sample_incident.chain_put(0, 0.0, 'user', 'alice')
    sample_incident.chain_update(0, done=True, result=200)
    sample_incident.chain_put(1, 180.0, 'user', 'alice')
    return sample_incident


def test_resume_chain_clock_is_idempotent(incident):
    started = datetime.now(UTC) - timedelta(seconds=60)
    incident.resume_chain_clock(since=started)
    incident.resume_chain_clock()

    assert incident.chain_resumed_at == started
    assert incident.chain_elapsed_seconds() == pytest.approx(60, abs=1)


def test_accumulate_chain_time_pauses_clock(incident):
    incident.chain_active_seconds = 30.0
    incident.chain_resumed_at = datetime.now(UTC) - timedelta(seconds=60)

    incident.accumulate_chain_time(datetime.now(UTC) - timedelta(hours=1))

    assert incident.chain_resumed_at is None
    assert incident.chain_active_seconds == pytest.approx(90, abs=1)
    assert incident.chain_elapsed_seconds() == pytest.approx(90, abs=1)


def test_accumulate_chain_time_without_clock_uses_updated(incident):
    incident.accumulate_chain_time(datetime.now(UTC) - timedelta(seconds=60))

    assert incident.chain_active_seconds == pytest.approx(60, abs=1)


@pytest.mark.asyncio
async def test_restart_keeps_elapsed_chain_time(incident):
    incident.chain_resumed_at = datetime.now(UTC) - timedelta(seconds=60)

    queue = await AsyncQueue.recreate_queue(SimpleNamespace(uniq_ids={incident.uniq_id: incident}))

    steps = _chain_steps(queue, incident.uniq_id)
    assert [item.identifier for item in steps] == [1]
    remaining = (steps[0].datetime - datetime.now(UTC)).total_seconds()
    assert remaining == pytest.approx(120, abs=2)


@pytest.mark.asyncio
async def test_restart_of_legacy_incident_counts_from_last_status_change(incident):
    incident.chain_resumed_at = None
    incident.chain_active_seconds = 0.0
    incident.updated = datetime.now(UTC) - timedelta(seconds=60)

    queue = await AsyncQueue.recreate_queue(SimpleNamespace(uniq_ids={incident.uniq_id: incident}))

    remaining = (_chain_steps(queue, incident.uniq_id)[0].datetime - datetime.now(UTC)).total_seconds()
    assert remaining == pytest.approx(120, abs=2)
    assert incident.chain_resumed_at == incident.updated


@pytest.mark.asyncio
async def test_restart_after_pause_counts_only_active_time(incident):
    incident.chain_resumed_at = datetime.now(UTC) - timedelta(seconds=20)
    incident.chain_active_seconds = 100.0

    queue = await AsyncQueue.recreate_queue(SimpleNamespace(uniq_ids={incident.uniq_id: incident}))

    remaining = (_chain_steps(queue, incident.uniq_id)[0].datetime - datetime.now(UTC)).total_seconds()
    assert remaining == pytest.approx(60, abs=2)


def test_chain_resumed_at_is_reset_with_chain(incident):
    incident.chain_resumed_at = datetime.now(UTC)
    incident.release()

    assert incident.chain_resumed_at is None
    assert 'chain_resumed_at' in incident.serialize()
