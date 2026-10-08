"""Exercise the application's state stores through an in-memory S3 client."""
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml
from botocore.exceptions import ClientError, EndpointConnectionError

from app.config.environment import EnvironmentConfig
from app.im.chain.ui_chains_store import UIChainsStore
from app.im.user_store import UserStore
from app.incident.incidents import Incidents
from app.incident.migrator import IncidentMigrator
from app.maintenance.store import MaintenanceStore
from app.storage import FileStorage, get_storage
from app.tools import NoAliasDumper
from app.ui.authentication.models.auth_session import AuthSession
from app.ui.authentication.session_store import FileSessionStore


@pytest.fixture
def remote_state(tmp_path, monkeypatch):
    config = EnvironmentConfig(data_path=str(tmp_path / 'local'),
                               storage_backend='s3', s3_bucket='state', s3_prefix='instance')
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
    app_config.messenger.type.value = 'slack'
    monkeypatch.setattr('app.incident.incidents.get_config', lambda: app_config)
    sample_incident.link = sample_incident.generate_link(incident_config.application_url)
    sample_incident.dump()
    filename = f'instance/incidents/{sample_incident.uniq_id}.yml'
    assert filename in objects
    restored = Incidents.create_or_load('slack', incident_config.application_url, incident_config.application_team)
    assert restored.get_by_uniq_id(sample_incident.uniq_id).serialize() == sample_incident.serialize()

    old_data = yaml.load(objects.pop(filename), Loader=yaml.CLoader)
    old_data['version'] = 'v3.6.0'
    old_data['chain'] = old_data.pop('chain_steps')
    objects['instance/incidents/legacy.yml'] = yaml.dump(old_data, Dumper=NoAliasDumper).encode()
    restored = Incidents.create_or_load('slack', incident_config.application_url, incident_config.application_team)
    assert 'instance/incidents/legacy.yml' not in objects
    assert yaml.safe_load(objects[filename])['version'] == 'v3.7.0'
    restored.del_by_uniq_id(sample_incident.uniq_id)
    assert filename not in objects
    assert not Path(config.data_path).exists()


def test_users_restart_and_filtering(remote_state):
    storage, config, objects = remote_state
    UserStore().save('U1', 'slack', {'full_name': 'José', 'username': 'jose'})
    UserStore().save('M1', 'mattermost', {'full_name': 'Maria'})
    restored = UserStore().get_all_users_by_type('slack')
    assert set(restored) == {'U1'}
    assert restored['U1']['full_name'] == 'José'
    assert 'instance/users/U1.yml' in objects
    assert storage.client.get_object.call_count == 2
    storage.client.head_object.assert_not_called()


def test_calendar_and_maintenance_restart_and_retention(remote_state):
    storage, config, objects = remote_state
    now = datetime.now(timezone.utc).replace(microsecond=0)
    start, end = (now + timedelta(hours=1)).isoformat(), (now + timedelta(hours=2)).isoformat()
    shift = {'id': 'shift', 'start': start, 'end': end, 'priority': 1, 'steps': [{'user': 'alice'}]}
    assert UIChainsStore().save_shifts('primary', [shift])
    assert UIChainsStore().load_shifts('primary')[0]['steps'] == [{'user': 'alice'}]
    window = {'id': 'window', 'start': start, 'end': end, 'matchers': ['service="db"'], 'comment': 'planned'}
    assert MaintenanceStore().save_windows([window])
    assert MaintenanceStore().load_windows()[0]['matchers'] == ['service="db"']
    assert {'instance/ui_chains/primary.ics', 'instance/maintenance/windows.ics'} <= objects.keys()
    assert UIChainsStore().prune_all(now + timedelta(days=1000)) == 1
    assert MaintenanceStore().prune_expired_windows(now + timedelta(days=1000)) == 1
    assert UIChainsStore().load_shifts('primary') == []
    assert MaintenanceStore().load_windows() == []


def test_sessions_restart_validation_and_expiry(remote_state):
    storage, config, objects = remote_state
    root = f'{config.data_path}/sessions'
    store = FileSessionStore(root)
    now = datetime.now(timezone.utc)
    session = AuthSession(session_id='a' * 64, user_id='U1', created_at=now, expires_at=now + timedelta(hours=1))
    store.save_session(session)
    assert FileSessionStore(root).load_session(session.session_id) == session
    assert store.load_session('../outside') is None
    invalid = session.model_copy(update={'session_id': '../outside'})
    with pytest.raises(ValueError, match='invalid session id'):
        store.save_session(invalid)
    objects[f'instance/sessions/{"b" * 64}.yaml'] = objects[f'instance/sessions/{session.session_id}.yaml']
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
    assert UIChainsStore().save_shifts('primary', [{'id': 'shift', 'start': start, 'end': end, 'steps': []}])
    assert MaintenanceStore().save_windows([{'id': 'window', 'start': start, 'end': end, 'matchers': ['service="db"']}])
    before = objects.copy()
    storage.client.get_object.side_effect = EndpointConnectionError(endpoint_url='https://unavailable.example')
    with pytest.raises(OSError):
        UIChainsStore().prune_all(now + timedelta(days=1000))
    with pytest.raises(OSError):
        MaintenanceStore().prune_expired_windows(now + timedelta(days=1000))
    assert objects == before


@pytest.mark.parametrize('failed_operation', ['delete_object', 'put_object'])
def test_interrupted_incident_migration_recovers_without_resurrection(remote_state, sample_incident, incident_config, monkeypatch, failed_operation):
    storage, config, objects = remote_state
    app_config = Mock(INCIDENT_ACTUAL_VERSION='v3.7.0')
    app_config.messenger.type.value = 'slack'
    monkeypatch.setattr('app.incident.incidents.get_config', lambda: app_config)
    data = sample_incident.serialize()
    data['version'] = 'v3.6.0'
    data['chain'] = data.pop('chain_steps')
    objects['instance/incidents/legacy.yml'] = yaml.dump(data, Dumper=NoAliasDumper).encode()
    operation = getattr(storage.client, failed_operation)
    original = operation.side_effect
    operation.side_effect = EndpointConnectionError(endpoint_url='https://unavailable.example')
    with pytest.raises(OSError):
        Incidents.create_or_load('slack', incident_config.application_url, incident_config.application_team)
    assert all(yaml.safe_load(content)['version'] == 'v3.6.0' for content in objects.values())
    operation.side_effect = original
    restored = Incidents.create_or_load('slack', incident_config.application_url, incident_config.application_team)
    assert len(restored.uniq_ids) == 1
    assert set(objects) == {f'instance/incidents/{sample_incident.uniq_id}.yml'}
    restored.del_by_uniq_id(sample_incident.uniq_id)
    assert Incidents.create_or_load('slack', incident_config.application_url, incident_config.application_team).uniq_ids == {}


@pytest.mark.parametrize('failed_operation', ['delete_object', 'put_object'])
def test_cancelled_downgrade_reconciles_filenames_on_restart(remote_state, sample_incident, incident_config, monkeypatch, failed_operation):
    storage, config, objects = remote_state
    app_config = Mock(INCIDENT_ACTUAL_VERSION='v3.7.0')
    app_config.messenger.type.value = 'slack'
    monkeypatch.setattr('app.incident.incidents.get_config', lambda: app_config)
    sample_incident.dump()
    operation = getattr(storage.client, failed_operation)
    original = operation.side_effect
    operation.side_effect = EndpointConnectionError(endpoint_url='https://unavailable.example')
    with pytest.raises(OSError):
        IncidentMigrator().migrate_file(sample_incident.get_current_filename(), sample_incident.serialize(), 'v3.7.0', 'v3.6.0')
    operation.side_effect = original
    restored = Incidents.create_or_load('slack', incident_config.application_url, incident_config.application_team)
    assert len(restored.uniq_ids) == 1
    assert set(objects) == {f'instance/incidents/{sample_incident.uniq_id}.yml'}
    restored.del_by_uniq_id(sample_incident.uniq_id)
    assert Incidents.create_or_load('slack', incident_config.application_url, incident_config.application_team).uniq_ids == {}
