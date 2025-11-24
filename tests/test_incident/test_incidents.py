"""
Unit tests for app.incident.incidents module.
"""
import uuid
from unittest.mock import Mock, patch

import pytest

from app.incident.incident import Incident, IncidentConfig
from app.incident.incidents import Incidents
from tests.utils import (
    create_alert_payload, create_test_datetime, create_mock_config,
    create_mock_event_loop
)


class TestIncidents:
    """Test cases for Incidents class."""

    @pytest.fixture
    def sample_incidents(self):
        """Create sample incidents for testing."""
        config = IncidentConfig(
            application_type="slack",
            application_url="https://test.slack.com",
            application_team="test-team"
        )

        # Use utility function for consistent datetime
        test_datetime = create_test_datetime()

        # Create alert payloads using utility function
        alert1_payload = create_alert_payload(
            status="firing",
            alertname="TestAlert1",
            service="api",
            severity="critical"
        )
        alert1_payload["groupLabels"] = {"alertname": "TestAlert1", "severity": "critical", "service": "api"}

        alert2_payload = create_alert_payload(
            status="resolved",
            alertname="TestAlert2",
            service="database",
            severity="warning"
        )
        alert2_payload["groupLabels"] = {"alertname": "TestAlert2", "severity": "warning", "service": "database"}

        incident1 = Incident(
            payload=alert1_payload,
            status="firing",
            channel_id="C123456789",
            config=config,
            status_update_datetime=test_datetime,
            assigned_user_id="U123456",
            assigned_user="testuser1",
            assigned_fullname="Test User 1",
            messenger_type="slack"
        )

        incident2 = Incident(
            payload=alert2_payload,
            status="resolved",
            channel_id="C987654321",
            config=config,
            status_update_datetime=test_datetime,
            assigned_user_id="U789012",
            assigned_user="testuser2",
            assigned_fullname="Test User 2",
            messenger_type="slack"
        )

        return [incident1, incident2]

    @pytest.fixture
    def incidents(self, sample_incidents):
        """Create Incidents instance for testing."""
        return Incidents(sample_incidents)

    def test_incidents_initialization(self, sample_incidents):
        """Test Incidents initialization."""
        incidents = Incidents(sample_incidents)

        assert len(incidents.uniq_ids) == 2
        # uniq_ids are stored as strings in the dictionary keys
        assert all(isinstance(uniq_id_key, str) for uniq_id_key in incidents.uniq_ids.keys())
        assert all(isinstance(incident, Incident) for incident in incidents.uniq_ids.values())

    def test_get_by_alert(self, incidents):
        """Test getting incident by alert."""
        alert = {
            'groupLabels': {
                'alertname': 'TestAlert1',
                'severity': 'critical',
                'service': 'api'
            }
        }

        incident = incidents.get(alert)

        assert incident is not None
        # The payload structure from create_alert_payload includes alerts array
        assert incident.payload['groupLabels']['alertname'] == 'TestAlert1'

    def test_get_by_alert_nonexistent(self, incidents):
        """Test getting non-existent incident by alert."""
        alert = {
            'groupLabels': {
                'alertname': 'NonExistentAlert',
                'severity': 'critical'
            }
        }

        incident = incidents.get(alert)

        assert incident is None

    def test_get_by_ts(self, incidents):
        """Test getting incident by timestamp."""
        # Get a timestamp from one of the incidents
        incident = list(incidents.uniq_ids.values())[0]
        incident.ts = "1234567890.123456"

        found_incident = incidents.get_by_ts("1234567890.123456")

        assert found_incident is not None
        assert found_incident.ts == "1234567890.123456"

    def test_get_by_ts_nonexistent(self, incidents):
        """Test getting incident by non-existent timestamp."""
        found_incident = incidents.get_by_ts("nonexistent_ts")

        assert found_incident is None

    def test_get_assigned_user_by_id_existing(self, incidents):
        """Test getting assigned user by ID when user exists."""
        # Find an incident with assigned user
        incident_with_user = None
        for incident in incidents.uniq_ids.values():
            if incident.assigned_user_id and incident.assigned_fullname:
                incident_with_user = incident
                break

        if incident_with_user:
            user_id = incident_with_user.assigned_user_id
            fullname = incidents.get_assigned_user_by_id(user_id)

            assert fullname == incident_with_user.assigned_fullname

    def test_get_assigned_user_by_id_nonexistent(self, incidents):
        """Test getting assigned user by ID when user doesn't exist."""
        fullname = incidents.get_assigned_user_by_id("nonexistent_user_id")

        assert fullname is None

    def test_get_assigned_user_by_id_empty_name(self, incidents):
        """Test getting assigned user by ID when name is empty."""
        # Create incident with empty fullname
        config = IncidentConfig(
            application_type="slack",
            application_url="https://test.slack.com",
            application_team="test-team"
        )

        # Use utility function for alert payload
        alert_payload = create_alert_payload(
            status="firing",
            alertname="TestAlert",
            severity="critical"
        )
        alert_payload["groupLabels"] = {"alertname": "TestAlert", "severity": "critical"}

        incident = Incident(
            payload=alert_payload,
            status="firing",
            channel_id="C123456789",
            config=config,
            status_update_datetime=create_test_datetime(),
            assigned_user_id="U999999",  # Different user ID
            assigned_user="testuser",
            assigned_fullname="",  # Empty fullname
            messenger_type="slack"
        )

        incidents.add(incident)

        fullname = incidents.get_assigned_user_by_id("U999999")

        assert fullname is None

    def test_add_incident(self, incidents):
        """Test adding incident to collection."""
        config = IncidentConfig(
            application_type="slack",
            application_url="https://test.slack.com",
            application_team="test-team"
        )

        # Use utility function for alert payload
        alert_payload = create_alert_payload(
            status="firing",
            alertname="NewAlert",
            severity="critical"
        )
        alert_payload["groupLabels"] = {"alertname": "NewAlert", "severity": "critical"}

        new_incident = Incident(
            payload=alert_payload,
            status="firing",
            channel_id="C111111111",
            config=config,
            status_update_datetime=create_test_datetime(),
            assigned_user_id="",
            assigned_user="",
            assigned_fullname="",
            messenger_type="slack"
        )

        initial_count = len(incidents.uniq_ids)
        incidents.add(new_incident)

        assert len(incidents.uniq_ids) == initial_count + 1
        assert new_incident.uniq_id in incidents.uniq_ids

    def test_del_by_uuid_existing(self, incidents):
        """Test deleting incident by UUID."""
        # Get an existing incident
        incident_uuid = list(incidents.uniq_ids.keys())[0]
        initial_count = len(incidents.uniq_ids)

        with patch('os.remove') as mock_remove, \
                patch('asyncio.get_event_loop') as mock_get_loop, \
                patch('app.incident.incidents.incident_ws'):
            # Use utility function for mock event loop
            mock_loop = create_mock_event_loop(running=True)
            mock_get_loop.return_value = mock_loop

            incidents.del_by_uniq_id(incident_uuid)

            assert len(incidents.uniq_ids) == initial_count - 1
            assert incident_uuid not in incidents.uniq_ids
            mock_remove.assert_called_once()

    @pytest.mark.xfail(reason="Known bug: code accesses incident.uuid when incident is None in logger.warning f-string")
    def test_del_by_uuid_nonexistent(self, incidents):
        """Test deleting non-existent incident."""
        initial_count = len(incidents.uniq_ids)

        # The code has a bug: it tries to access incident.uuid when incident is None
        # in the f-string f'Incident with uuid {incident.uuid} not found...'
        # Since f-strings are evaluated immediately, we can't prevent the AttributeError
        # by mocking logger. We'll catch the error and verify the expected behavior.
        with patch('os.remove') as mock_remove:
            try:
                incidents.del_by_uniq_id("nonexistent_uuid")
            except AttributeError as e:
                # Expected error due to code bug: incident.uuid accessed when incident is None
                if "'NoneType' object has no attribute 'uuid'" in str(e):
                    # Verify that the incident was not removed (count unchanged)
                    assert len(incidents.uniq_ids) == initial_count
                    mock_remove.assert_not_called()
                    # Re-raise to trigger xfail
                    raise
                raise

            # If no error occurred, verify normal behavior
            assert len(incidents.uniq_ids) == initial_count  # Should not change
            mock_remove.assert_not_called()

    def test_del_by_uuid_file_not_found(self, incidents):
        """Test deleting incident when file doesn't exist."""
        incident_uuid = list(incidents.uniq_ids.keys())[0]

        with patch('os.remove', side_effect=FileNotFoundError) as mock_remove, \
                patch('app.incident.incidents.logger') as mock_logger:
            incidents.del_by_uniq_id(incident_uuid)

            mock_remove.assert_called_once()
            mock_logger.error.assert_called_once()

    def test_del_by_uuid_no_event_loop(self, incidents):
        """Test deleting incident when no event loop is running."""
        incident_uuid = list(incidents.uniq_ids.keys())[0]

        with patch('os.remove') as mock_remove, \
                patch('asyncio.get_event_loop', side_effect=RuntimeError("No event loop")):
            incidents.del_by_uniq_id(incident_uuid)

            mock_remove.assert_called_once()

    def test_serialize(self, incidents):
        """Test serializing incidents."""
        serialized = incidents.serialize()

        assert isinstance(serialized, dict)
        assert len(serialized) == len(incidents.uniq_ids)

        for uuid, incident_data in serialized.items():
            assert isinstance(incident_data, dict)
            assert 'status' in incident_data
            assert 'channel_id' in incident_data
            assert 'payload' in incident_data

    def test_get_table(self, incidents):
        """Test getting table data."""
        params = {}
        table_data = incidents.get_active_table(params)

        assert isinstance(table_data, list)
        assert len(table_data) == len(incidents.uniq_ids)

        for row in table_data:
            assert isinstance(row, dict)

    @patch('app.incident.incidents.get_config')
    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('os.walk')
    @patch('app.incident.incidents.Incident.load')
    @patch('builtins.open', create=True)
    @patch('yaml.load')
    def test_create_or_load_success(self, mock_yaml_load, mock_open, mock_load, mock_walk, mock_makedirs,
                                    mock_exists, mock_get_config):
        """Test successful creation or loading of incidents."""
        # Use utility function for mock config
        mock_config = create_mock_config(
            messenger_type="slack",
            incidents_path="/test/incidents"
        )
        mock_get_config.return_value = mock_config

        mock_exists.return_value = True
        mock_walk.return_value = [
            ('/test/incidents', [], ['incident1.yml', 'incident2.yml'])
        ]

        # Mock YAML content
        mock_yaml_load.return_value = {'version': 'v3.2.0'}

        # Mock incident loading
        mock_incident = Mock()
        mock_incident.messenger_type = 'slack'
        mock_load.return_value = mock_incident

        incidents = Incidents.create_or_load(
            application_type="slack",
            application_url="https://test.slack.com",
            application_team="test-team"
        )

        assert isinstance(incidents, Incidents)
        mock_makedirs.assert_not_called()  # Directory already exists

    @patch('app.incident.incidents.get_config')
    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('os.walk')
    @patch('app.incident.incidents.Incident.load')
    @patch('builtins.open', create=True)
    @patch('yaml.load')
    def test_create_or_load_create_directory(self, mock_yaml_load, mock_open, mock_load, mock_walk, mock_makedirs,
                                             mock_exists, mock_get_config):
        """Test creating incidents directory when it doesn't exist."""
        # Use utility function for mock config
        mock_config = create_mock_config(
            messenger_type="slack",
            incidents_path="/test/incidents"
        )
        mock_get_config.return_value = mock_config

        mock_exists.return_value = False
        mock_walk.return_value = [('/test/incidents', [], [])]

        # Mock YAML content
        mock_yaml_load.return_value = {'version': 'v3.2.0'}

        # Mock incident loading
        mock_incident = Mock()
        mock_incident.messenger_type = 'slack'
        mock_load.return_value = mock_incident

        incidents = Incidents.create_or_load(
            application_type="slack",
            application_url="https://test.slack.com",
            application_team="test-team"
        )

        assert isinstance(incidents, Incidents)
        mock_makedirs.assert_called_once_with('/test/incidents')

    @patch('app.incident.incidents.get_config')
    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('os.walk')
    @patch('app.incident.incidents.Incident.load')
    @patch('builtins.open', create=True)
    @patch('yaml.load')
    def test_create_or_load_different_messenger_type(self, mock_yaml_load, mock_open, mock_load, mock_walk,
                                                     mock_makedirs,
                                                     mock_exists, mock_get_config):
        """Test loading incidents with different messenger type."""
        # Use utility function for mock config
        mock_config = create_mock_config(
            messenger_type="slack",
            incidents_path="/test/incidents"
        )
        mock_get_config.return_value = mock_config

        mock_exists.return_value = True
        mock_walk.return_value = [
            ('/test/incidents', [], ['incident1.yml'])
        ]

        # Mock YAML content
        mock_yaml_load.return_value = {'version': 'v3.2.0'}

        # Mock incident with different messenger type
        mock_incident = Mock()
        mock_incident.messenger_type = 'mattermost'  # Different from config
        mock_load.return_value = mock_incident

        incidents = Incidents.create_or_load(
            application_type="slack",
            application_url="https://test.slack.com",
            application_team="test-team"
        )

        assert isinstance(incidents, Incidents)
        assert len(incidents.uniq_ids) == 0  # Should not include different messenger type

    @patch('app.incident.incidents.get_config')
    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('os.walk')
    @patch('app.incident.incidents.IncidentMigrator')
    @patch('app.incident.incidents.Incident.load')
    @patch('builtins.open', create=True)
    @patch('yaml.load')
    def test_create_or_load_with_migration(self, mock_yaml_load, mock_open, mock_load, mock_migrator_class, mock_walk,
                                           mock_makedirs,
                                           mock_exists, mock_get_config):
        """Test loading incidents with migration."""
        # Use utility function for mock config
        mock_config = create_mock_config(
            messenger_type="slack",
            incidents_path="/test/incidents"
        )
        mock_get_config.return_value = mock_config

        mock_exists.return_value = True
        mock_walk.return_value = [
            ('/test/incidents', [], ['incident1.yml'])
        ]

        # Mock YAML content with old version
        mock_yaml_load.return_value = {'version': 'v2.0.0'}

        # Mock incident loading
        mock_incident = Mock()
        mock_incident.messenger_type = 'slack'
        mock_load.return_value = mock_incident

        # Mock migrator
        mock_migrator = Mock()
        mock_migrator_class.return_value = mock_migrator

        incidents = Incidents.create_or_load(
            application_type="slack",
            application_url="https://test.slack.com",
            application_team="test-team"
        )

        assert isinstance(incidents, Incidents)
        mock_migrator_class.assert_called_once()
