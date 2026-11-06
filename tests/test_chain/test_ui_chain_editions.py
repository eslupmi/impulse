from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from app.im.chain.ui_chains_store import UIChainsStore
from community.app.im.chain.conditions import validate_step as validate_community_step


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr('app.im.chain.conditions.validate_step', validate_community_step)
    with patch('app.im.chain.ui_chains_store.get_environment_config') as environment, \
            patch('app.im.chain.ui_chains_store.get_config') as config:
        environment.return_value.data_path = environment.return_value.storage_root = str(tmp_path)
        config.return_value.incident.timeouts.get.return_value = '7d'
        yield UIChainsStore()


def _shift(steps, start='2026-11-06T00:00:00Z', end='2026-11-07T00:00:00Z'):
    return {'id': 'saved', 'start': start, 'end': end, 'steps': steps}


@pytest.mark.parametrize('steps', [
    [{'user': 'alice', 'if': "severity == 'critical'"}],
    [{'user': 'alice', 'if': 'invalid'}],
    [{'user': 'alice', 'wait': '5m'}],
    [{'wait': 'invalid'}],
    {'user': 'alice'},
])
def test_rejects_invalid_or_unavailable_steps_before_creating_file(store, steps):
    success, saved = store.upsert_shift('main', _shift(steps))

    assert not success
    assert saved == []
    assert not Path(store._calendar_path('main')).exists()


@pytest.mark.parametrize('operation', ['replace', 'delete', 'prune', 'active', 'preflight'])
@pytest.mark.parametrize('condition', ["severity == 'critical'", 'invalid'])
def test_unsupported_saved_shift_remains_readable_and_unchanged(store, operation, condition):
    assert store._write_shifts('main', [_shift([{'user': 'alice', 'if': condition}])])
    path = Path(store._calendar_path('main'))
    original = path.read_bytes()
    now = datetime(2026, 11, 6, 12, tzinfo=UTC)

    if operation == 'replace':
        success, _ = store.upsert_shift('main', _shift([{'user': 'bob'}]))
        assert not success
    elif operation == 'delete':
        success, _ = store.delete_shift('main', 'saved')
        assert not success
    elif operation == 'prune':
        assert store.prune_expired_shifts('main', datetime(2027, 1, 1, tzinfo=UTC)) == 0
    elif operation == 'active':
        with pytest.raises(ValueError):
            store.get_steps_for_now('main', now)
    else:
        with pytest.raises(ValueError, match="Invalid saved UI chain 'main'"):
            store.validate_persisted_steps()

    assert path.read_bytes() == original
    assert store.load_shifts('main')[0]['steps'][0]['if'] == condition


def test_prune_all_preflights_inactive_shifts_before_removing_any_file(store):
    assert store._write_shifts('expired', [_shift(
        [{'user': 'alice'}], '2020-01-01T00:00:00Z', '2020-01-02T00:00:00Z',
    )])
    assert store._write_shifts('inactive', [_shift(
        [{'user': 'alice', 'if': "severity == 'critical'"}],
        '2030-01-01T00:00:00Z', '2030-01-02T00:00:00Z',
    )])
    originals = {Path(store._calendar_path(name)): Path(store._calendar_path(name)).read_bytes()
                 for name in ['expired', 'inactive']}

    with pytest.raises(ValueError, match="Invalid saved UI chain 'inactive'"):
        store.prune_all(datetime(2026, 11, 6, tzinfo=UTC))

    assert all(path.read_bytes() == content for path, content in originals.items())


@pytest.mark.asyncio
async def test_primary_initialization_preflights_before_creating_runtime_objects():
    from app.lifespan import create_main_objects

    with patch('app.lifespan.get_config'), \
            patch('app.lifespan.ui_chains_store.validate_persisted_steps', side_effect=ValueError('unsupported')), \
            patch('app.lifespan.generate_route') as generate_route, \
            patch('app.lifespan.get_application') as get_application, \
            pytest.raises(ValueError, match='unsupported'):
        await create_main_objects(Mock())

    generate_route.assert_not_called()
    get_application.assert_not_called()
