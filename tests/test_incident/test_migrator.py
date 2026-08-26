"""
Unit tests for app.incident.migrator module.
"""
import os
from datetime import datetime, timezone
from unittest.mock import Mock, patch, mock_open

import pytest

from app.incident.freeze import FreezeSource
from app.incident.incident import Incident
from app.incident.migrator import IncidentMigrator
from tests.utils import create_mock_config, create_alert_payload


class TestIncidentMigrator:
    """Test cases for IncidentMigrator class."""

    @pytest.fixture
    def migrator(self):
        """Create IncidentMigrator instance for testing."""
        return IncidentMigrator()

    def test_migrator_initialization(self, migrator):
        """Test IncidentMigrator initialization."""
        assert migrator is not None
        assert hasattr(migrator, 'MIGRATION_CHAIN')
        assert hasattr(migrator, '_migration_methods')
        assert 'v0.4_to_v3.0.0' in migrator._migration_methods
        assert 'v3.0.0_to_v3.2.0' in migrator._migration_methods
        assert 'v3.2.0_to_v3.4.0' in migrator._migration_methods
        assert 'v3.4.0_to_v3.6.0' in migrator._migration_methods
        assert 'v3.6.0_to_v3.7.0' in migrator._migration_methods
        assert 'v3.7.0_to_v3.6.0' in migrator._migration_methods
        assert 'v3.6.0_to_v3.7.0' in migrator._filename_migration_methods
        assert 'v3.7.0_to_v3.6.0' in migrator._filename_migration_methods

    def test_migrate_file_success(self, migrator):
        """Test successful file migration."""
        # Use utility function for alert payload
        alert_payload = create_alert_payload(
            status="firing",
            alertname="TestAlert",
            severity="critical"
        )

        from datetime import datetime, timezone
        incident_data = {
            'last_state': alert_payload['alerts'][0]['labels'],  # Extract labels from alert
            'status': 'firing',
            'groupLabels': alert_payload.get('groupLabels', {}),
            'created': datetime.now(timezone.utc)  # Add created to avoid None error
        }

        with patch('builtins.open', mock_open()) as mock_file, \
                patch('yaml.dump') as mock_yaml_dump, \
                patch('app.incident.migrator.os.rename'), \
                patch('app.incident.migrator.get_config') as mock_get_config:
            # Use utility function for mock config
            mock_config = create_mock_config(messenger_type="slack")
            mock_get_config.return_value = mock_config

            migrator.migrate_file('/test/incident.yml', incident_data, 'v0.4', 'v3.7.0')

            mock_file.assert_called_once_with('/test/incident.yml', 'w')
            mock_yaml_dump.assert_called_once()

            # Check that the migrated data has the correct structure
            call_args = mock_yaml_dump.call_args[0]
            migrated_data = call_args[0]
            assert migrated_data['version'] == 'v3.7.0'
            assert migrated_data['payload'] == incident_data['last_state']
            assert migrated_data['messenger_type'] == 'slack'

    def test_migrate_data_v0_4_to_v3_7_0(self, migrator):
        """Test migrating data from v0.4 to v3.7.0 (chained)."""
        # Use utility function for alert payload
        alert_payload = create_alert_payload(
            status="firing",
            alertname="TestAlert",
            severity="critical"
        )

        from datetime import datetime, timezone
        incident_data = {
            'last_state': alert_payload['alerts'][0]['labels'],  # Extract labels from alert
            'status': 'firing',
            'channel_id': 'C123456789',
            'groupLabels': alert_payload.get('groupLabels', {}),
            'created': datetime.now(timezone.utc)  # Add created to avoid None error
        }

        with patch('app.incident.migrator.get_config') as mock_get_config:
            # Use utility function for mock config
            mock_config = create_mock_config(messenger_type="slack")
            mock_get_config.return_value = mock_config

            result = migrator._migrate_data(incident_data, 'v0.4', 'v3.7.0')

            assert result['version'] == 'v3.7.0'
            assert result['payload'] == incident_data['last_state']
            assert result['messenger_type'] == 'slack'
            assert result['status'] == 'firing'
            assert result['channel_id'] == 'C123456789'

    def test_migrate_data_no_migration_chain(self, migrator):
        """Test migrating data when no migration chain is defined."""
        # Temporarily clear the migration chain
        original_chain = migrator.MIGRATION_CHAIN
        migrator.MIGRATION_CHAIN = {}

        try:
            incident_data = {'status': 'firing'}
            result = migrator._migrate_data(incident_data, 'v1.0', 'v2.0')

            assert result['version'] == 'v2.0'
            assert result['status'] == 'firing'
        finally:
            migrator.MIGRATION_CHAIN = original_chain

    def test_get_migration_path(self, migrator):
        """Test getting migration path between versions."""
        path = migrator._get_migration_path('v0.4', 'v3.7.0')

        assert path == ['v0.4', 'v3.0.0', 'v3.2.0', 'v3.4.0', 'v3.6.0', 'v3.7.0']

    def test_apply_single_migration(self, migrator):
        """Test applying a single migration step."""
        # Use utility function for alert payload
        alert_payload = create_alert_payload(
            status="firing",
            alertname="TestAlert"
        )

        incident_data = {
            'last_state': alert_payload['alerts'][0]['labels'],  # Extract labels from alert
            'status': 'firing'
        }

        with patch('app.incident.migrator.get_config') as mock_get_config:
            # Use utility function for mock config
            mock_config = create_mock_config(messenger_type="slack")
            mock_get_config.return_value = mock_config

            result = migrator._apply_single_migration(incident_data, 'v0.4', 'v3.0.0')

            assert result['version'] == 'v3.0.0'
            assert result['payload'] == incident_data['last_state']
            assert result['messenger_type'] == 'slack'

    def test_migrate_v0_4_to_v3_0_0(self, migrator):
        """Test the specific v0.4 to v3.0.0 migration method."""
        # Use utility function for alert payload
        alert_payload = create_alert_payload(
            status="firing",
            alertname="TestAlert",
            severity="critical"
        )

        incident_data = {
            'last_state': alert_payload['alerts'][0]['labels'],  # Extract labels from alert
            'status': 'firing',
            'channel_id': 'C123456789'
        }

        with patch('app.incident.migrator.get_config') as mock_get_config:
            # Use utility function for mock config
            mock_config = create_mock_config(messenger_type="slack")
            mock_get_config.return_value = mock_config

            result = migrator._migrate_v0_4_to_v3_0_0(incident_data)

            assert result['payload'] == incident_data['last_state']
            assert result['messenger_type'] == 'slack'
            assert result['status'] == 'firing'
            assert result['channel_id'] == 'C123456789'

    def test_migrate_v0_4_to_v3_0_0_preserves_other_fields(self, migrator):
        """Test that v0.4 to v3.0.0 migration preserves other fields."""
        # Use utility function for alert payload
        alert_payload = create_alert_payload(
            status="firing",
            alertname="TestAlert",
            severity="critical"
        )

        incident_data = {
            'last_state': alert_payload['alerts'][0]['labels'],  # Extract labels from alert
            'status': 'firing',
            'channel_id': 'C123456789',
            'assigned_user': 'testuser',
            'assigned_fullname': 'Test User',
            'link': 'https://slack.com/archives/C123456789/p1234567890',
            'ts': '1234567890.123456',
            'uuid': 'test-uuid-123',
            'custom_field': 'custom_value'
        }

        with patch('app.incident.migrator.get_config') as mock_get_config:
            # Use utility function for mock config
            mock_config = create_mock_config(messenger_type="slack")
            mock_get_config.return_value = mock_config

            result = migrator._migrate_v0_4_to_v3_0_0(incident_data)

            assert result['payload'] == incident_data['last_state']
            assert result['messenger_type'] == 'slack'
            assert result['status'] == 'firing'
            assert result['channel_id'] == 'C123456789'
            assert result['assigned_user'] == 'testuser'
            assert result['assigned_fullname'] == 'Test User'
            assert result['link'] == 'https://slack.com/archives/C123456789/p1234567890'
            assert result['ts'] == '1234567890.123456'
            assert result['uuid'] == 'test-uuid-123'
            assert result['custom_field'] == 'custom_value'

    def test_migrate_v0_4_to_v3_0_0_with_empty_last_state(self, migrator):
        """Test v0.4 to v3.0.0 migration when last_state is empty."""
        incident_data = {
            'last_state': {},
            'status': 'firing',
            'channel_id': 'C123456789'
        }

        with patch('app.incident.migrator.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.messenger.type.value = 'slack'
            mock_get_config.return_value = mock_config

            result = migrator._migrate_v0_4_to_v3_0_0(incident_data)

            assert result['payload'] == {}  # empty last_state becomes empty payload
            assert result['messenger_type'] == 'slack'
            assert result['status'] == 'firing'
            assert result['channel_id'] == 'C123456789'

    def test_migrate_v3_4_0_to_v3_6_0_sets_time_source_for_old_manual_freeze(self, migrator):
        from datetime import datetime, timezone

        frozen_until = datetime.now(timezone.utc)
        incident_data = {
            'status': 'firing',
            'frozen_until': frozen_until,
        }

        result = migrator._migrate_v3_4_0_to_v3_6_0(incident_data)

        assert result['frozen_until'] == frozen_until
        assert result['frozen_until_source'] == FreezeSource.TIME.value

    def test_migrate_v3_4_0_to_v3_6_0_preserves_existing_source(self, migrator):
        incident_data = {
            'status': 'firing',
            'frozen_until': None,
            'frozen_until_source': FreezeSource.MAINTENANCE.value,
        }

        result = migrator._migrate_v3_4_0_to_v3_6_0(incident_data)

        assert result['frozen_until_source'] == FreezeSource.MAINTENANCE.value

    def test_migrate_v3_4_0_to_v3_6_0_sets_empty_source_for_non_time_freeze(self, migrator):
        incident_data = {
            'status': 'firing',
            'parents': ['parent-incident'],
        }

        result = migrator._migrate_v3_4_0_to_v3_6_0(incident_data)

        assert result['frozen_until_source'] is None

    def test_migrate_file_with_logging(self, migrator):
        """Test that migrate_file logs appropriate messages."""
        # Use utility function for alert payload
        alert_payload = create_alert_payload(
            status="firing",
            alertname="TestAlert"
        )

        from datetime import datetime, timezone
        incident_data = {
            'last_state': alert_payload['alerts'][0]['labels'],  # Extract labels from alert
            'status': 'firing',
            'groupLabels': alert_payload.get('groupLabels', {}),
            'created': datetime.now(timezone.utc)  # Add created to avoid None error
        }

        with patch('builtins.open', mock_open()), \
                patch('yaml.dump'), \
                patch('app.incident.migrator.os.rename'), \
                patch('app.incident.migrator.get_config') as mock_get_config, \
                patch('app.incident.migrator.logger') as mock_logger:
            # Use utility function for mock config
            mock_config = create_mock_config(messenger_type="slack")
            mock_get_config.return_value = mock_config

            migrator.migrate_file('/test/incident.yml', incident_data, 'v0.4', 'v3.7.0')

            # Check that logging was called
            assert mock_logger.info.call_count >= 2
            mock_logger.info.assert_any_call('Migrating incident.yml from v0.4 to v3.7.0')

    def test_migrate_filename_open_incident(self, migrator):
        uniq_id = 'test-uniq-id-open'
        incident_data = {'uniq_id': uniq_id, 'version': 'v3.7.0'}
        old_path = os.path.join('/test/incidents', 'old-uuid.yml')
        new_path = os.path.join('/test/incidents', f'{uniq_id}.yml')

        with patch('app.incident.migrator.os.rename') as mock_rename:
            result = migrator._migrate_filename_v3_6_0_to_v3_7_0(old_path, incident_data)

        mock_rename.assert_called_once_with(old_path, new_path)
        assert result == new_path

    def test_migrate_filename_closed_incident(self, migrator):
        uniq_id = 'test-uniq-id-closed'
        incident_data = {'uniq_id': uniq_id, 'version': 'v3.7.0'}
        old_path = os.path.join('/test/incidents', 'old-uuid__2025_01_15__14_30_45.yml')
        new_path = os.path.join('/test/incidents', f'{uniq_id}.yml')

        with patch('app.incident.migrator.os.rename') as mock_rename:
            result = migrator._migrate_filename_v3_6_0_to_v3_7_0(old_path, incident_data)

        mock_rename.assert_called_once_with(old_path, new_path)
        assert result == new_path

    def test_migrate_filename_idempotent(self, migrator):
        uniq_id = 'already-migrated-id'
        file_path = os.path.join('/test/incidents', f'{uniq_id}.yml')
        incident_data = {'uniq_id': uniq_id, 'version': 'v3.7.0'}

        with patch('app.incident.migrator.os.rename') as mock_rename:
            result = migrator._migrate_filename_v3_6_0_to_v3_7_0(file_path, incident_data)

        mock_rename.assert_not_called()
        assert result == file_path

    def test_reshape_chain_steps_renames_fields(self, migrator):
        data = {
            'version': 'v3.6.0',
            'chain': [
                {'delay': 0.0, 'type': 'user', 'identifier': 'alice', 'done': True, 'result': 200},
                {'delay': 300.0, 'type': 'webhook', 'identifier': 'notify', 'done': True, 'result': 201},
                {'delay': 600.0, 'type': 'webhook', 'identifier': 'missing', 'done': True, 'result': None},
            ],
        }

        result = migrator._migrate_v3_6_0_to_v3_7_0(data)

        assert 'chain' not in result
        assert len(result['chain_steps']) == 3
        assert result['chain_steps'][0]['name'] == 'user'
        assert result['chain_steps'][0]['value'] == 'alice'
        assert result['chain_steps'][1]['name'] == 'webhook'
        assert result['chain_steps'][1]['value'] == 'notify'
        assert result['chain_steps'][1]['status'] == 'ok'
        assert result['chain_steps'][2]['status'] is None

    def test_reshape_chain_steps_idempotent(self, migrator):
        data = {
            'version': 'v3.7.0',
            'chain_steps': [
                {'delay': 0.0, 'name': 'user', 'value': 'alice', 'done': False, 'result': None, 'status': None},
            ],
        }

        result = IncidentMigrator.reshape_chain_steps(data)

        assert result['chain_steps'][0]['name'] == 'user'
        assert result['chain_steps'][0]['value'] == 'alice'

    def test_migrate_file_returns_renamed_path(self, migrator):
        uniq_id = 'renamed-uniq-id'
        incident_data = {
            'status': 'firing',
            'uniq_id': uniq_id,
            'version': 'v3.6.0',
        }
        old_path = os.path.join('/test/incidents', 'old-uuid.yml')
        new_path = os.path.join('/test/incidents', f'{uniq_id}.yml')

        with patch('builtins.open', mock_open()), \
                patch('yaml.dump'), \
                patch('app.incident.migrator.os.rename'):
            result = migrator.migrate_file(
                old_path,
                incident_data,
                'v3.6.0',
                'v3.7.0',
            )

        assert result == new_path

    def test_get_migration_path_downgrade(self, migrator):
        path = migrator._get_migration_path('v3.7.0', 'v3.6.0')
        assert path == ['v3.7.0', 'v3.6.0']

    def test_reshape_chain_steps_v3_6_reverses_fields(self, migrator):
        data = {
            'version': 'v3.7.0',
            'chain_steps': [
                {'delay': 0.0, 'name': 'user', 'value': 'alice', 'done': True, 'result': 200, 'status': 'ok'},
                {'delay': 300.0, 'name': 'webhook', 'value': 'notify', 'done': True, 'result': 201, 'status': 'ok'},
                {'delay': 600.0, 'name': 'webhook', 'value': 'missing', 'done': True, 'result': None, 'status': None},
            ],
        }

        result = migrator._migrate_v3_7_0_to_v3_6_0(data)

        assert 'chain_steps' not in result
        assert len(result['chain']) == 3
        assert result['chain'][0] == {
            'delay': 0.0, 'type': 'user', 'identifier': 'alice', 'done': True, 'result': 200,
        }
        assert result['chain'][1] == {
            'delay': 300.0, 'type': 'webhook', 'identifier': 'notify', 'done': True, 'result': 201,
        }
        assert result['chain'][2] == {
            'delay': 600.0, 'type': 'webhook', 'identifier': 'missing', 'done': True, 'result': None,
        }
        assert 'status' not in result['chain'][0]
        assert 'status' not in result['chain'][1]

    def test_reshape_chain_steps_v3_6_no_chain(self, migrator):
        data = {'version': 'v3.7.0', 'status': 'firing'}
        result = IncidentMigrator.reshape_chain_steps_v3_6(data)
        assert 'chain' not in result
        assert 'chain_steps' not in result

    def test_migrate_filename_downgrade_open(self, migrator):
        group_labels = {'alertname': 'TestAlert'}
        uuid = Incident.gen_uuid(group_labels)
        uniq_id = 'some-uniq-id'
        incident_data = {
            'uniq_id': uniq_id,
            'status': 'firing',
            'payload': {'groupLabels': group_labels},
        }
        old_path = os.path.join('/test/incidents', f'{uniq_id}.yml')
        new_path = os.path.join('/test/incidents', f'{uuid}.yml')

        with patch('app.incident.migrator.os.rename') as mock_rename:
            result = migrator._migrate_filename_v3_7_0_to_v3_6_0(old_path, incident_data)

        mock_rename.assert_called_once_with(old_path, new_path)
        assert result == new_path

    def test_migrate_filename_downgrade_closed(self, migrator):
        group_labels = {'alertname': 'ClosedAlert'}
        uuid = Incident.gen_uuid(group_labels)
        uniq_id = 'closed-uniq-id'
        closed = datetime(2025, 1, 15, 14, 30, 45, tzinfo=timezone.utc)
        incident_data = {
            'uniq_id': uniq_id,
            'status': 'closed',
            'closed': closed,
            'payload': {'groupLabels': group_labels},
        }
        old_path = os.path.join('/test/incidents', f'{uniq_id}.yml')
        new_path = os.path.join('/test/incidents', f'{uuid}__2025_01_15__14_30_45.yml')

        with patch('app.incident.migrator.os.rename') as mock_rename:
            result = migrator._migrate_filename_v3_7_0_to_v3_6_0(old_path, incident_data)

        mock_rename.assert_called_once_with(old_path, new_path)
        assert result == new_path

    def test_migrate_filename_downgrade_idempotent(self, migrator):
        group_labels = {'alertname': 'SameName'}
        uuid = Incident.gen_uuid(group_labels)
        file_path = os.path.join('/test/incidents', f'{uuid}.yml')
        incident_data = {
            'status': 'firing',
            'payload': {'groupLabels': group_labels},
        }

        with patch('app.incident.migrator.os.rename') as mock_rename:
            result = migrator._migrate_filename_v3_7_0_to_v3_6_0(file_path, incident_data)

        mock_rename.assert_not_called()
        assert result == file_path

    def test_migrate_file_downgrade_returns_restored_path(self, migrator):
        group_labels = {'alertname': 'DowngradePath'}
        uuid = Incident.gen_uuid(group_labels)
        uniq_id = 'downgrade-uniq'
        incident_data = {
            'status': 'firing',
            'uniq_id': uniq_id,
            'version': 'v3.7.0',
            'payload': {'groupLabels': group_labels},
            'chain_steps': [
                {'delay': 0.0, 'name': 'user', 'value': 'alice', 'done': False, 'result': None, 'status': None},
            ],
        }
        old_path = os.path.join('/test/incidents', f'{uniq_id}.yml')
        new_path = os.path.join('/test/incidents', f'{uuid}.yml')

        with patch('builtins.open', mock_open()), \
                patch('yaml.dump'), \
                patch('app.incident.migrator.os.rename'):
            result = migrator.migrate_file(
                old_path,
                incident_data,
                'v3.7.0',
                'v3.6.0',
            )

        assert result == new_path

    def test_upgrade_downgrade_round_trip_chain(self, migrator):
        group_labels = {'alertname': 'RoundTrip'}
        uuid = Incident.gen_uuid(group_labels)
        uniq_id = 'round-trip-uniq'
        original_chain = [
            {'delay': 0.0, 'type': 'user', 'identifier': 'alice', 'done': True, 'result': 200},
            {'delay': 300.0, 'type': 'webhook', 'identifier': 'notify', 'done': True, 'result': 201},
        ]
        incident_data = {
            'status': 'firing',
            'uniq_id': uniq_id,
            'version': 'v3.6.0',
            'payload': {'groupLabels': group_labels},
            'chain': [step.copy() for step in original_chain],
        }

        upgraded = migrator._migrate_data(incident_data, 'v3.6.0', 'v3.7.0')
        assert upgraded['version'] == 'v3.7.0'
        assert 'chain' not in upgraded
        assert upgraded['chain_steps'][0]['name'] == 'user'
        assert upgraded['chain_steps'][0]['value'] == 'alice'

        downgraded = migrator._migrate_data(upgraded, 'v3.7.0', 'v3.6.0')
        assert downgraded['version'] == 'v3.6.0'
        assert 'chain_steps' not in downgraded
        assert downgraded['chain'] == original_chain

        uuid_path = os.path.join('/test/incidents', f'{uuid}.yml')
        uniq_path = os.path.join('/test/incidents', f'{uniq_id}.yml')
        with patch('app.incident.migrator.os.rename'):
            upgraded_path = migrator._migrate_filename_v3_6_0_to_v3_7_0(
                uuid_path,
                {'uniq_id': uniq_id},
            )
            restored_path = migrator._migrate_filename_v3_7_0_to_v3_6_0(
                upgraded_path,
                {'status': 'firing', 'payload': {'groupLabels': group_labels}},
            )
        assert upgraded_path == uniq_path
        assert restored_path == uuid_path

    def test_resolve_downgrade_target_empty_arg(self, migrator):
        with patch('app.incident.migrator.get_config') as mock_get_config:
            mock_config = create_mock_config()
            mock_config.INCIDENT_ACTUAL_VERSION = 'v3.7.0'
            mock_get_config.return_value = mock_config
            assert IncidentMigrator.resolve_downgrade_target('') == 'v3.6.0'
            assert IncidentMigrator.resolve_downgrade_target(None) == 'v3.6.0'

    def test_resolve_downgrade_target_release_tag(self, migrator):
        with patch('app.incident.migrator.get_config') as mock_get_config:
            mock_config = create_mock_config()
            mock_config.INCIDENT_ACTUAL_VERSION = 'v3.7.0'
            mock_get_config.return_value = mock_config
            assert IncidentMigrator.resolve_downgrade_target('v3.6.3') == 'v3.6.0'
            assert IncidentMigrator.resolve_downgrade_target('v3.6.0') == 'v3.6.0'

    def test_resolve_downgrade_target_below_floor(self, migrator):
        with patch('app.incident.migrator.get_config') as mock_get_config:
            mock_config = create_mock_config()
            mock_config.INCIDENT_ACTUAL_VERSION = 'v3.7.0'
            mock_get_config.return_value = mock_config
            with pytest.raises(ValueError, match='below supported floor'):
                IncidentMigrator.resolve_downgrade_target('v3.4.0')

    def test_resolve_downgrade_target_unknown(self, migrator):
        with patch('app.incident.migrator.get_config') as mock_get_config:
            mock_config = create_mock_config()
            mock_config.INCIDENT_ACTUAL_VERSION = 'v3.7.0'
            mock_get_config.return_value = mock_config
            with pytest.raises(ValueError, match='Unknown version'):
                IncidentMigrator.resolve_downgrade_target('not-a-version')
