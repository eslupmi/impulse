"""Exercise the application's state stores through an in-memory S3 client."""
import io
import os
from datetime import datetime, timedelta, timezone
from functools import partial
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml
from botocore.exceptions import ClientError, EndpointConnectionError
from icalendar import Calendar

from app.config.environment import EnvironmentConfig
from app.im.chain.ui_chains_store import UIChainsStore
from app.im.user_store import UserStore
from app.incident.incidents import Incidents
from app.maintenance.store import MaintenanceStore
from app.migrator import IncidentMigrator, MaintenanceMigrator
from app.storage import FileStorage, get_storage
from app.tools import NoAliasDumper
from app.ui.authentication.models.auth_session import AuthSession
from app.ui.authentication.session_store import FileSessionStore


LEGACY_MAINTENANCE = (
    b'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n'
    b'BEGIN:VEVENT\r\nUID:window\r\n'
    b'DTSTART:20260620T080000Z\r\nDTEND:20260620T120000Z\r\n'
    b'DTSTAMP:20260601T101112Z\r\nX-MATCHER:service="db"\r\nEND:VEVENT\r\n'
    b'BEGIN:VEVENT\r\nUID:a/b\r\n'
    b'DTSTART:20260621T080000Z\r\nDTEND:20260621T120000Z\r\n'
    b'X-MATCHER:service="cache"\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n'
)


@pytest.fixture
def remote_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = EnvironmentConfig(data_path=str(tmp_path / 'local'),
                               storage_backend='s3', s3_bucket='state')
    monkeypatch.setattr('app.config.environment._env_config', config)
    storage = get_storage(config)
    objects = {}
    client = Mock()

    def get_object(*, Key, **kwargs):
        if Key not in objects:
            raise ClientError({'Error': {'Code': 'NoSuchKey'}}, 'GetObject')
        return {'Body': io.BytesIO(objects[Key])}

    def listing(*, Prefix, **kwargs):
        return {'Contents': [{'Key': key} for key in sorted(objects) if key.startswith(Prefix)]}

    client.get_object.side_effect = get_object
    client.put_object.side_effect = lambda Key, Body, **kwargs: objects.update({Key: Body})
    client.delete_object.side_effect = lambda Key, **kwargs: objects.pop(Key, None)
    client.copy_object.side_effect = lambda Key, CopySource, **kwargs: objects.update({Key: objects[CopySource['Key']]})
    client.list_objects_v2.side_effect = listing
    client.get_paginator.return_value.paginate.side_effect = lambda **kwargs: [listing(**kwargs)]
    storage._client = client
    return storage, config, objects


def test_incident_restart_migration_and_deletion(remote_state, sample_incident, incident_config, monkeypatch):
    storage, config, objects = remote_state
    app_config = Mock(INCIDENT_ACTUAL_VERSION='v3.7.0')
    app_config.messenger.type = 'slack'
    monkeypatch.setattr('app.incident.incidents.get_config', lambda: app_config)
    sample_incident.link = sample_incident.generate_link(incident_config.application_url)
    sample_incident.dump()
    filename = f'incidents/{sample_incident.uniq_id}.yml'
    assert filename in objects
    restored = Incidents.create_or_load('slack', incident_config.application_url, incident_config.application_team)
    assert restored.get_by_uniq_id(sample_incident.uniq_id).serialize() == sample_incident.serialize()

    old_data = yaml.load(objects.pop(filename), Loader=yaml.CLoader)
    old_data['version'] = 'v3.6.0'
    old_data['chain'] = old_data.pop('chain_steps')
    objects['incidents/legacy.yml'] = yaml.dump(old_data, Dumper=NoAliasDumper).encode()
    restored = Incidents.create_or_load('slack', incident_config.application_url, incident_config.application_team)
    assert 'incidents/legacy.yml' not in objects
    assert yaml.safe_load(objects[filename])['version'] == 'v3.7.0'
    restored.del_by_uniq_id(sample_incident.uniq_id)
    assert filename not in objects
    assert not any(Path().iterdir())


def test_users_restart_and_filtering(remote_state):
    storage, config, objects = remote_state
    UserStore().save('U1', 'slack', {'full_name': 'José', 'username': 'jose'})
    UserStore().save('M1', 'mattermost', {'full_name': 'Maria'})
    restored = UserStore().get_all_users_by_type('slack')
    assert set(restored) == {'U1'}
    assert restored['U1']['full_name'] == 'José'
    assert 'users/U1.yml' in objects
    assert storage.client.get_object.call_count == 2
    storage.client.head_object.assert_not_called()


def test_calendar_and_maintenance_restart_and_retention(remote_state):
    storage, config, objects = remote_state
    now = datetime.now(timezone.utc).replace(microsecond=0)
    start, end = (now + timedelta(hours=1)).isoformat(), (now + timedelta(hours=2)).isoformat()
    shift = {'id': 'shift', 'start': start, 'end': end, 'priority': 1, 'steps': [{'user': 'alice'}]}
    assert UIChainsStore().upsert_shift('primary', shift)[0]
    assert UIChainsStore().load_shifts('primary')[0]['steps'] == [{'user': 'alice'}]
    window = {'id': 'window', 'start': start, 'end': end, 'matchers': ['service="db"'],
              'comment': 'planned', 'owner_id': 'U1'}
    assert MaintenanceStore().upsert_window(window, {'U1'})[0]
    assert MaintenanceStore().load_windows()[0]['matchers'] == ['service="db"']
    assert {'ui_chains/primary.ics', 'maintenance/window.ics'} <= objects.keys()
    assert UIChainsStore().prune_all(now + timedelta(days=1000)) == 1
    assert MaintenanceStore().prune_expired_windows(now + timedelta(days=1000)) == 1
    assert UIChainsStore().load_shifts('primary') == []
    assert MaintenanceStore().load_windows() == []


def test_remote_maintenance_migration_preserves_calendars_and_filenames(remote_state):
    _, config, objects = remote_state
    legacy_key = 'maintenance/windows.ics'
    objects[legacy_key] = LEGACY_MAINTENANCE
    store = MaintenanceStore()
    store.migrate()
    assert set(objects) == {'maintenance/window.ics', 'maintenance/a%2Fb.ics'}
    original = objects.copy()
    calendar = Calendar.from_ical(objects['maintenance/window.ics'])
    assert str(calendar.get('x-impulse-version')) == MaintenanceMigrator.ACTUAL_VERSION
    assert calendar.walk('VEVENT')[0]['dtstamp'].to_ical() == b'20260601T101112Z'
    assert Calendar.from_ical(objects['maintenance/a%2Fb.ics']).walk('VEVENT')[0].get('dtstamp') is None
    assert {window['id'] for window in MaintenanceStore().load_windows()} == {'window', 'a/b'}
    assert all('_dtstamp' not in window for window in store.load_windows())

    MaintenanceMigrator().downgrade(store, MaintenanceMigrator.LEGACY_VERSION)
    assert set(objects) == {legacy_key}
    assert str(Calendar.from_ical(objects[legacy_key]).get('x-impulse-version')) == MaintenanceMigrator.LEGACY_VERSION
    MaintenanceStore().migrate()
    assert objects == original
    assert not any(Path().iterdir())


@pytest.mark.parametrize('failed_operation', ['put_object', 'delete_object'])
@pytest.mark.parametrize('direction', ['upgrade', 'downgrade'])
def test_remote_maintenance_migration_failures_are_recoverable(remote_state, failed_operation, direction):
    storage, _, objects = remote_state
    objects['maintenance/windows.ics'] = LEGACY_MAINTENANCE
    store = MaintenanceStore()
    migration = store.migrate
    if direction == 'downgrade':
        store.migrate()
        migration = partial(MaintenanceMigrator().downgrade, store, MaintenanceMigrator.LEGACY_VERSION)
    before = objects.copy()
    operation = getattr(storage.client, failed_operation)
    original = operation.side_effect
    operation.side_effect = EndpointConnectionError(endpoint_url='https://unavailable.example')
    with pytest.raises(OSError):
        migration()
    assert before.items() <= objects.items()
    operation.side_effect = original

    restored = MaintenanceStore()
    restored.migrate()
    assert set(objects) == {'maintenance/window.ics', 'maintenance/a%2Fb.ics'}
    assert {window['id'] for window in restored.load_windows()} == {'window', 'a/b'}
    assert restored.delete_window('window')[0]
    assert restored.delete_window('a/b')[0]
    MaintenanceStore().migrate()
    assert objects == {}


@pytest.mark.parametrize('recovery', ['upgrade', 'downgrade'])
def test_remote_maintenance_interrupted_rename_cannot_resurrect_deleted_window(remote_state, recovery):
    storage, _, objects = remote_state
    objects['maintenance/windows.ics'] = LEGACY_MAINTENANCE
    store = MaintenanceStore()
    store.migrate()
    before = objects.copy()
    timestamp_key = 'maintenance/2026-10-20-20-44-00-000000.ics'
    objects[timestamp_key] = objects.pop('maintenance/window.ics')
    original = storage.client.delete_object.side_effect
    storage.client.delete_object.side_effect = EndpointConnectionError(endpoint_url='https://unavailable.example')
    with pytest.raises(OSError):
        store.migrate()
    assert objects['maintenance/window.ics'] == objects[timestamp_key]
    storage.client.delete_object.side_effect = original

    restored = MaintenanceStore()
    if recovery == 'downgrade':
        MaintenanceMigrator().downgrade(restored, MaintenanceMigrator.LEGACY_VERSION)
        assert set(objects) == {'maintenance/windows.ics'}
    restored.migrate()
    assert objects == before
    assert restored.delete_window('window')[0]
    assert restored.delete_window('a/b')[0]
    MaintenanceStore().migrate()
    assert objects == {}


def test_remote_maintenance_rename_preserves_occupied_target(remote_state):
    _, _, objects = remote_state
    objects['maintenance/windows.ics'] = LEGACY_MAINTENANCE
    store = MaintenanceStore()
    store.migrate()
    timestamp_key = 'maintenance/2026-10-20-20-44-00-000000.ics'
    objects[timestamp_key] = objects.pop('maintenance/window.ics')
    objects['maintenance/window.ics'] = b'unreadable existing record'
    before = objects.copy()
    with pytest.raises(FileExistsError):
        store.migrate()
    assert objects == before


def test_sessions_restart_validation_and_expiry(remote_state):
    storage, config, objects = remote_state
    root = os.path.join(config.data_path, 'sessions')
    store = FileSessionStore(root)
    now = datetime.now(timezone.utc)
    session = AuthSession(session_id='a' * 64, user_id='U1', created_at=now, expires_at=now + timedelta(hours=1))
    store.save_session(session)
    assert FileSessionStore(root).load_session(session.session_id) == session
    assert store.load_session('../outside') is None
    invalid = session.model_copy(update={'session_id': '../outside'})
    with pytest.raises(ValueError, match='invalid session id'):
        store.save_session(invalid)
    objects[f'sessions/{"b" * 64}.yaml'] = objects[f'sessions/{session.session_id}.yaml']
    assert store.load_session('b' * 64) is None
    expired = session.model_copy(update={'session_id': 'c' * 64, 'expires_at': now - timedelta(seconds=1)})
    store.save_session(expired)
    assert store.cleanup_expired() == 1
    assert store.load_session(expired.session_id) is None
    store.delete_session(session.session_id)
    assert store.load_session(session.session_id) is None
    storage.client.head_object.assert_not_called()


def test_filesystem_sessions_keep_atomic_writes(tmp_path):
    now = datetime.now(timezone.utc)
    session = AuthSession(session_id='a' * 64, user_id='U1', created_at=now, expires_at=now + timedelta(hours=1))
    store = FileSessionStore(str(tmp_path), storage=FileStorage())
    import os
    with patch('app.ui.authentication.session_store.os.replace', wraps=os.replace) as replace:
        store.save_session(session)
        replace.assert_called_once()
    assert store.load_session(session.session_id) == session
    assert [path.name for path in tmp_path.iterdir()] == [session.session_id + '.yaml']


def test_remote_calendar_read_failure_cannot_erase_stored_data(remote_state):
    storage, config, objects = remote_state
    now = datetime.now(timezone.utc)
    start, end = now.isoformat(), (now + timedelta(hours=1)).isoformat()
    chains_store = UIChainsStore()
    maintenance_store = MaintenanceStore()
    future = now + timedelta(days=1000)
    assert chains_store.upsert_shift('primary', {'id': 'shift', 'start': start, 'end': end, 'steps': []})[0]
    window = {'id': 'window', 'start': start, 'end': end, 'matchers': ['service="db"'],
              'comment': 'planned', 'owner_id': 'U1'}
    assert maintenance_store.upsert_window(window, {'U1'})[0]
    before = objects.copy()
    storage.client.get_object.side_effect = EndpointConnectionError(endpoint_url='https://unavailable.example')
    with pytest.raises(OSError):
        chains_store.prune_all(future)
    with pytest.raises(OSError):
        maintenance_store.prune_expired_windows(future)
    assert objects == before


@pytest.mark.parametrize('failed_operation', ['delete_object', 'put_object'])
def test_interrupted_incident_migration_recovers_without_resurrection(remote_state, sample_incident, incident_config, monkeypatch, failed_operation):
    storage, config, objects = remote_state
    app_config = Mock(INCIDENT_ACTUAL_VERSION='v3.7.0')
    app_config.messenger.type = 'slack'
    monkeypatch.setattr('app.incident.incidents.get_config', lambda: app_config)
    data = sample_incident.serialize()
    data['version'] = 'v3.6.0'
    data['chain'] = data.pop('chain_steps')
    objects['incidents/legacy.yml'] = yaml.dump(data, Dumper=NoAliasDumper).encode()
    operation = getattr(storage.client, failed_operation)
    original = operation.side_effect
    operation.side_effect = EndpointConnectionError(endpoint_url='https://unavailable.example')
    with pytest.raises(OSError):
        Incidents.create_or_load('slack', incident_config.application_url, incident_config.application_team)
    assert all(yaml.safe_load(content)['version'] == 'v3.6.0' for content in objects.values())
    operation.side_effect = original
    restored = Incidents.create_or_load('slack', incident_config.application_url, incident_config.application_team)
    assert len(restored.uniq_ids) == 1
    assert set(objects) == {f'incidents/{sample_incident.uniq_id}.yml'}
    restored.del_by_uniq_id(sample_incident.uniq_id)
    assert Incidents.create_or_load('slack', incident_config.application_url, incident_config.application_team).uniq_ids == {}


@pytest.mark.parametrize('failed_operation', ['delete_object', 'put_object'])
def test_cancelled_downgrade_reconciles_filenames_on_restart(remote_state, sample_incident, incident_config, monkeypatch, failed_operation):
    storage, config, objects = remote_state
    app_config = Mock(INCIDENT_ACTUAL_VERSION='v3.7.0')
    app_config.messenger.type = 'slack'
    monkeypatch.setattr('app.incident.incidents.get_config', lambda: app_config)
    sample_incident.dump()
    migrator = IncidentMigrator()
    file_path = sample_incident.get_current_filename()
    data = sample_incident.serialize()
    operation = getattr(storage.client, failed_operation)
    original = operation.side_effect
    operation.side_effect = EndpointConnectionError(endpoint_url='https://unavailable.example')
    with pytest.raises(OSError):
        migrator.migrate_file(file_path, data, 'v3.7.0', 'v3.6.0')
    operation.side_effect = original
    restored = Incidents.create_or_load('slack', incident_config.application_url, incident_config.application_team)
    assert len(restored.uniq_ids) == 1
    assert set(objects) == {f'incidents/{sample_incident.uniq_id}.yml'}
    restored.del_by_uniq_id(sample_incident.uniq_id)
    assert Incidents.create_or_load('slack', incident_config.application_url, incident_config.application_team).uniq_ids == {}
