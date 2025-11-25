"""
Unit tests for app.incident.migrator module.
"""
from unittest.mock import Mock, patch, mock_open

import pytest

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
                patch('app.incident.migrator.get_config') as mock_get_config:
            # Use utility function for mock config
            mock_config = create_mock_config(messenger_type="slack")
            mock_get_config.return_value = mock_config

            migrator.migrate_file('/test/incident.yml', incident_data, 'v0.4', 'v3.2.0')

            mock_file.assert_called_once_with('/test/incident.yml', 'w')
            mock_yaml_dump.assert_called_once()

            # Check that the migrated data has the correct structure
            call_args = mock_yaml_dump.call_args[0]
            migrated_data = call_args[0]
            assert migrated_data['version'] == 'v3.2.0'
            assert migrated_data['payload'] == incident_data['last_state']
            assert migrated_data['messenger_type'] == 'slack'

    def test_migrate_data_v0_4_to_v3_2_0(self, migrator):
        """Test migrating data from v0.4 to v3.2.0 (chained)."""
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

            result = migrator._migrate_data(incident_data, 'v0.4', 'v3.2.0')

            assert result['version'] == 'v3.2.0'
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
        path = migrator._get_migration_path('v0.4', 'v3.2.0')

        assert path == ['v0.4', 'v3.0.0', 'v3.2.0']

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
                patch('app.incident.migrator.get_config') as mock_get_config, \
                patch('app.incident.migrator.logger') as mock_logger:
            # Use utility function for mock config
            mock_config = create_mock_config(messenger_type="slack")
            mock_get_config.return_value = mock_config

            migrator.migrate_file('/test/incident.yml', incident_data, 'v0.4', 'v3.2.0')

            # Check that logging was called
            assert mock_logger.info.call_count == 2
            mock_logger.info.assert_any_call('Migrating incident.yml from v0.4 to v3.2.0')
            mock_logger.info.assert_any_call('Successfully migrated incident.yml')
