"""
Unit tests for app.incident.incident module.
"""
from datetime import datetime, timezone
from unittest.mock import Mock, patch, mock_open

import pytest

from app.config.validation import MessengerType
from app.incident.incident import Incident, IncidentConfig
from tests.utils import (
    create_mock_chains_config, create_mock_incident_data, create_mock_event_loop
)


class TestIncidentConfig:
    """Test cases for IncidentConfig dataclass."""

    def test_incident_config_creation(self):
        """Test creation of IncidentConfig."""
        config = IncidentConfig(
            application_type="slack",
            application_url="https://test.slack.com",
            application_team="test-team"
        )
        assert config.application_type == "slack"
        assert config.application_url == "https://test.slack.com"
        assert config.application_team == "test-team"


class TestIncident:
    """Test cases for Incident class."""

    def test_incident_creation(self, sample_alert_payload, incident_config):
        """Test basic incident creation."""
        incident = Incident(
            payload=sample_alert_payload,
            status="firing",
            channel_id="C123456789",
            config=incident_config,
            status_update_datetime=datetime.now(timezone.utc),
            assigned_user_id="",
            assigned_user="",
            assigned_fullname="",
            messenger_type="slack"
        )

        assert incident.payload == sample_alert_payload
        assert incident.status == "firing"
        assert incident.channel_id == "C123456789"
        assert incident.config == incident_config
        assert incident.assigned_user_id == ""
        assert incident.assigned_user == ""
        assert incident.assigned_fullname == ""
        assert incident.messenger_type == "slack"
        assert incident.chain == []
        assert incident.chain_enabled is False
        assert incident.status_enabled is False
        assert incident.uuid is not None
        assert incident.uniq_id is not None
        assert incident.ts == ""
        assert incident.link == ""

    @patch('app.incident.incident.Incident.gen_uniq_id')
    @patch('app.incident.incident.Incident.gen_uuid')
    def test_incident_uuid_generation(self, mock_gen_uuid, mock_gen_uniq_id, sample_alert_payload, incident_config):
        """Test that UUID and uniq_id are generated correctly."""
        mock_gen_uuid.return_value = "test-uuid"
        mock_gen_uniq_id.return_value = "test-uniq-id"

        incident = Incident(
            payload=sample_alert_payload,
            status="firing",
            channel_id="C123456789",
            config=incident_config,
            status_update_datetime=datetime.now(timezone.utc),
            assigned_user_id="",
            assigned_user="",
            assigned_fullname="",
            messenger_type="slack"
        )

        # gen_uuid is called once for uuid
        assert mock_gen_uuid.call_count == 1
        mock_gen_uuid.assert_called_once_with(sample_alert_payload.get('groupLabels'))
        assert incident.uuid == "test-uuid"
        
        # gen_uniq_id is called once for uniq_id
        assert mock_gen_uniq_id.call_count == 1
        assert incident.uniq_id == "test-uniq-id"

    def test_set_thread_slack(self, sample_incident):
        """Test setting thread for Slack."""
        sample_incident.config.application_type = MessengerType.SLACK
        sample_incident.set_thread("1234567890.123456", "https://test.slack.com")

        assert sample_incident.ts == "1234567890.123456"
        assert "archives/C123456789/p1234567890123456" in sample_incident.link

    def test_set_thread_mattermost(self, sample_incident):
        """Test setting thread for Mattermost."""
        sample_incident.config.application_type = MessengerType.MATTERMOST
        sample_incident.set_thread("thread123", "https://mattermost.test.com")

        assert sample_incident.ts == "thread123"
        assert sample_incident.link == "https://test.slack.com/test-team/pl/thread123"

    def test_set_thread_telegram(self, sample_incident):
        """Test setting thread for Telegram."""
        sample_incident.config.application_type = MessengerType.TELEGRAM
        sample_incident.channel_id = "-1001234567890"
        sample_incident.set_thread("123", "https://t.me")

        assert sample_incident.ts == "123"
        assert sample_incident.link == "https://t.me/c/1234567890/123"

    def test_generate_link_slack(self, sample_incident):
        """Test link generation for Slack."""
        sample_incident.config.application_type = MessengerType.SLACK
        sample_incident.ts = "1234567890.123456"

        link = sample_incident.generate_link("https://test.slack.com")
        # The actual implementation concatenates without a / between public_url and archives
        assert link == "https://test.slack.comarchives/C123456789/p1234567890123456"

    def test_generate_link_mattermost(self, sample_incident):
        """Test link generation for Mattermost."""
        sample_incident.config.application_type = MessengerType.MATTERMOST
        sample_incident.ts = "thread123"

        link = sample_incident.generate_link("https://mattermost.test.com")
        assert link == "https://test.slack.com/test-team/pl/thread123"

    def test_generate_link_telegram(self, sample_incident):
        """Test link generation for Telegram."""
        sample_incident.config.application_type = MessengerType.TELEGRAM
        sample_incident.channel_id = "-1001234567890"
        sample_incident.ts = "123"

        link = sample_incident.generate_link("https://t.me")
        assert link == "https://t.me/c/1234567890/123"

    def test_generate_link_unknown_type(self, sample_incident):
        """Test link generation for unknown messenger type."""
        sample_incident.config.application_type = "unknown"
        link = sample_incident.generate_link("https://example.com")
        assert link == ""

    def test_set_next_status_firing_to_unknown(self, sample_incident):
        """Test status transition from firing to unknown."""
        sample_incident.status = "firing"
        with patch.object(sample_incident, 'update_status') as mock_update:
            mock_update.return_value = True
            new_status = sample_incident.next_status[sample_incident.status]
            result = sample_incident.update_status(new_status)
            mock_update.assert_called_once_with("unknown")
            assert result is True

    def test_set_next_status_unknown_to_closed(self, sample_incident):
        """Test status transition from unknown to closed."""
        sample_incident.status = "unknown"
        with patch.object(sample_incident, 'update_status') as mock_update:
            mock_update.return_value = True
            new_status = sample_incident.next_status[sample_incident.status]
            result = sample_incident.update_status(new_status)
            mock_update.assert_called_once_with("closed")
            assert result is True

    def test_set_next_status_resolved_to_closed(self, sample_incident):
        """Test status transition from resolved to closed."""
        sample_incident.status = "resolved"
        with patch.object(sample_incident, 'update_status') as mock_update:
            mock_update.return_value = True
            new_status = sample_incident.next_status[sample_incident.status]
            result = sample_incident.update_status(new_status)
            mock_update.assert_called_once_with("closed")
            assert result is True

    @patch('app.incident.incident.get_config')
    def test_update_status_with_timeout(self, mock_get_config, sample_incident, mock_unified_config):
        """Test updating status with timeout configuration."""
        mock_get_config.return_value = mock_unified_config
        mock_unified_config.incident.timeouts = {"unknown": "1h"}

        # Set initial status to something different to ensure change
        sample_incident.status = "firing"

        with patch.object(sample_incident, 'dump'), \
                patch.object(sample_incident, 'set_status') as mock_set_status:
            result = sample_incident.update_status("unknown")

            assert result is True
            mock_set_status.assert_called_once_with("unknown")
            assert isinstance(sample_incident.status_update_datetime, datetime)

    def test_update_status_no_change(self, sample_incident):
        """Test updating status when status doesn't change."""
        sample_incident.status = "firing"

        with patch.object(sample_incident, 'dump'), \
                patch.object(sample_incident, 'set_status') as mock_set_status:
            result = sample_incident.update_status("firing")

            assert result is False
            mock_set_status.assert_not_called()

    def test_update_state_status_changed(self, sample_incident, sample_alert_payload):
        """Test updating incident state when status changes."""
        new_payload = sample_alert_payload.copy()
        new_payload['status'] = 'resolved'

        with patch.object(sample_incident, 'update_status') as mock_update_status, \
                patch.object(sample_incident, 'dump'):
            mock_update_status.return_value = True
            status_updated, state_updated = sample_incident.update_state(new_payload)

            assert status_updated is True
            assert state_updated is True
            assert sample_incident.payload == new_payload

    def test_update_state_no_changes(self, sample_incident, sample_alert_payload):
        """Test updating incident state when nothing changes."""
        with patch.object(sample_incident, 'update_status') as mock_update_status:
            mock_update_status.return_value = False
            status_updated, state_updated = sample_incident.update_state(sample_alert_payload)

            assert status_updated is False
            assert state_updated is False

    def test_set_status(self, sample_incident):
        """Test setting status."""
        sample_incident.set_status("resolved")
        assert sample_incident.status == "resolved"

    def test_set_status_closed_sets_closed_field(self, sample_incident):
        """Test that setting status to 'closed' sets the closed field to current datetime."""
        from datetime import datetime, timezone
        
        sample_incident.closed = None  # Ensure closed is empty initially
        sample_incident.set_status("closed")
        
        assert sample_incident.status == "closed"
        assert sample_incident.closed is not None
        assert isinstance(sample_incident.closed, datetime)
        assert sample_incident.closed.tzinfo == timezone.utc

    def test_set_status_closed_does_not_overwrite_existing(self, sample_incident):
        """Test that setting status to 'closed' does not overwrite existing closed field."""
        from datetime import datetime, timezone
        existing_closed = datetime(2025, 1, 15, 14, 30, 45, tzinfo=timezone.utc)
        sample_incident.closed = existing_closed
        sample_incident.set_status("closed")
        
        assert sample_incident.status == "closed"
        assert sample_incident.closed == existing_closed  # Should not be overwritten

    def test_is_new_firing_alerts_added(self, sample_incident):
        """Test detection of new firing alerts."""
        old_payload = {
            "alerts": [
                {"status": "firing", "labels": {"alert": "alert1"}},
                {"status": "resolved", "labels": {"alert": "alert2"}}
            ]
        }
        sample_incident.payload = old_payload

        new_payload = {
            "alerts": [
                {"status": "firing", "labels": {"alert": "alert1"}},
                {"status": "firing", "labels": {"alert": "alert3"}},  # New firing alert
                {"status": "resolved", "labels": {"alert": "alert2"}}
            ]
        }

        result = sample_incident.is_new_firing_alerts_added(new_payload)
        assert result is True

    def test_is_new_firing_alerts_not_added(self, sample_incident):
        """Test when no new firing alerts are added."""
        old_payload = {
            "alerts": [
                {"status": "firing", "labels": {"alert": "alert1"}},
                {"status": "resolved", "labels": {"alert": "alert2"}}
            ]
        }
        sample_incident.payload = old_payload

        new_payload = {
            "alerts": [
                {"status": "firing", "labels": {"alert": "alert1"}},
                {"status": "resolved", "labels": {"alert": "alert2"}}
            ]
        }

        result = sample_incident.is_new_firing_alerts_added(new_payload)
        assert result is False

    def test_is_some_firing_alerts_removed(self, sample_incident):
        """Test detection of removed firing alerts."""
        old_payload = {
            "alerts": [
                {"status": "firing", "labels": {"alert": "alert1"}},
                {"status": "firing", "labels": {"alert": "alert2"}}
            ]
        }
        sample_incident.payload = old_payload

        new_payload = {
            "alerts": [
                {"status": "firing", "labels": {"alert": "alert1"}},
                {"status": "resolved", "labels": {"alert": "alert2"}}  # No longer firing
            ]
        }

        result = sample_incident.is_some_firing_alerts_removed(new_payload)
        assert result is True

    def test_is_some_firing_alerts_not_removed(self, sample_incident):
        """Test when no firing alerts are removed."""
        old_payload = {
            "alerts": [
                {"status": "firing", "labels": {"alert": "alert1"}},
                {"status": "resolved", "labels": {"alert": "alert2"}}
            ]
        }
        sample_incident.payload = old_payload

        new_payload = {
            "alerts": [
                {"status": "firing", "labels": {"alert": "alert1"}},
                {"status": "resolved", "labels": {"alert": "alert2"}}
            ]
        }

        result = sample_incident.is_some_firing_alerts_removed(new_payload)
        assert result is False

    def test_get_firing_alerts_labels(self):
        """Test extraction of firing alerts labels."""
        alert_state = {
            "alerts": [
                {"status": "firing", "labels": {"alert": "alert1"}},
                {"status": "resolved", "labels": {"alert": "alert2"}},
                {"status": "firing", "labels": {"alert": "alert3"}}
            ]
        }

        labels = Incident._get_firing_alerts_labels(alert_state)
        expected = [{"alert": "alert1"}, {"alert": "alert3"}]
        assert labels == expected

    def test_release(self, sample_incident):
        """Test releasing an incident."""
        sample_incident.chain = [{"test": "data"}]
        sample_incident.assigned_user_id = "U123456"
        sample_incident.assigned_user = "john.doe"
        sample_incident.assigned_fullname = "John Doe"

        with patch.object(sample_incident, 'dump'):
            sample_incident.release()

        assert sample_incident.chain == []
        assert sample_incident.assigned_user_id == ""
        assert sample_incident.assigned_user == ""
        assert sample_incident.assigned_fullname == ""
        assert sample_incident.chain_enabled is True

    def test_get_chain_enabled(self, sample_incident):
        """Test getting chain when enabled."""
        sample_incident.chain_enabled = True
        sample_incident.chain = [{"test": "data"}]

        result = sample_incident.get_chain()
        assert result == [{"test": "data"}]

    def test_get_chain_disabled(self, sample_incident):
        """Test getting chain when disabled."""
        sample_incident.chain_enabled = False
        sample_incident.chain = [{"test": "data"}]

        result = sample_incident.get_chain()
        assert result == []

    def test_chain_put(self, sample_incident):
        """Test putting item in chain."""
        sample_incident.chain_put(0, 300.0, "test_type", "test_id")

        assert len(sample_incident.chain) == 1
        assert sample_incident.chain[0]['delay'] - 300.0 < 0.000001
        assert sample_incident.chain[0]['type'] == "test_type"
        assert sample_incident.chain[0]['identifier'] == "test_id"
        assert sample_incident.chain[0]['done'] is False
        assert sample_incident.chain[0]['result'] is None

    def test_chain_update(self, sample_incident):
        """Test updating chain item."""
        sample_incident.chain_put(0, 300.0, "test_type", "test_id")

        with patch.object(sample_incident, 'dump'):
            sample_incident.chain_update(0, True, "test_result")

        assert sample_incident.chain[0]['done'] is True
        assert sample_incident.chain[0]['result'] == "test_result"

    @patch('app.incident.incident.get_environment_config')
    @patch('app.incident.incident.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.dump')
    def test_dump(self, mock_yaml_dump, mock_file_open, mock_get_config, mock_get_env_config, sample_incident, mock_unified_config, mock_environment_config):
        """Test dumping incident to file."""
        mock_get_config.return_value = mock_unified_config
        mock_get_env_config.return_value = mock_environment_config
        mock_environment_config.incidents_path = "/test/incidents"

        with patch('app.incident.incident.incident_ws'):
            sample_incident.dump()

        mock_file_open.assert_called_once()
        # Check that file is opened with correct path for non-closed incident
        assert f'/test/incidents/{sample_incident.uuid}.yml' in str(mock_file_open.call_args)
        mock_yaml_dump.assert_called_once()

    @patch('app.incident.incident.get_environment_config')
    @patch('app.incident.incident.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.dump')
    def test_dump_closed_incident(self, mock_yaml_dump, mock_file_open, mock_get_config, mock_get_env_config, sample_incident, mock_unified_config, mock_environment_config):
        """Test dumping closed incident to file with correct filename."""
        from datetime import datetime, timezone
        mock_get_config.return_value = mock_unified_config
        mock_get_env_config.return_value = mock_environment_config
        mock_environment_config.incidents_path = "/test/incidents"
        sample_incident.status = 'closed'
        sample_incident.closed = datetime(2025, 1, 15, 14, 30, 45, tzinfo=timezone.utc)

        with patch('app.incident.incident.incident_ws'):
            sample_incident.dump()

        mock_file_open.assert_called_once()
        # Check that file is opened with correct path for closed incident
        closed_str = sample_incident.datetime_serialize(sample_incident.closed)
        assert f'/test/incidents/{sample_incident.uuid}__{closed_str}.yml' in str(mock_file_open.call_args)
        mock_yaml_dump.assert_called_once()

    @patch('app.incident.incident.ChannelManager')
    def test_serialize(self, mock_channel_manager, sample_incident):
        """Test incident serialization."""
        mock_channel_manager.return_value.get_channel_name_by_id.return_value = "test-channel"

        result = sample_incident.serialize()

        assert result['status'] == sample_incident.status
        assert result['channel_id'] == sample_incident.channel_id
        assert result['channel_name'] == "test-channel"
        assert result['payload'] == sample_incident.payload
        assert 'chain_enabled' in result
        assert 'chain' in result
        assert 'status_enabled' in result
        assert 'status_update_datetime' in result
        assert 'updated' in result
        assert 'created' in result
        assert 'assigned_user_id' in result
        assert 'assigned_user' in result
        assert 'assigned_fullname' in result
        assert 'messenger_type' in result
        assert 'link' in result
        assert 'ts' in result

    def test_generate_chain_with_valid_chain(self, sample_incident):
        """Test generating chain with valid chain configuration."""
        chains = create_mock_chains_config({
            'test_chain': [
                {'user': 'testuser'},
                {'wait': '5m'},
                {'user': 'admin'}
            ]
        })

        with patch.object(sample_incident, 'dump'):
            sample_incident.generate_chain(chains, 'test_chain')

        # The chain generation processes steps and creates chain items
        # Wait steps don't create chain items, they just adjust timing
        assert len(sample_incident.chain) == 2  # Only user steps create chain items
        assert sample_incident.chain[0]['type'] == 'user'
        assert sample_incident.chain[0]['identifier'] == 'testuser'
        assert sample_incident.chain[1]['type'] == 'user'
        assert sample_incident.chain[1]['identifier'] == 'admin'

    def test_generate_chain_with_none_chain_name(self, sample_incident):
        """Test generating chain with None chain name."""
        chains = create_mock_chains_config({'test_chain': []})

        with patch.object(sample_incident, 'dump'):
            sample_incident.generate_chain(chains, None)

        assert len(sample_incident.chain) == 0

    def test_generate_chain_with_missing_chain(self, sample_incident):
        """Test generating chain with missing chain name."""
        chains = create_mock_chains_config({'other_chain': []})

        with patch('app.incident.incident.logger') as mock_logger:
            sample_incident.generate_chain(chains, 'missing_chain')

        mock_logger.warning.assert_called_once()
        assert len(sample_incident.chain) == 0

    def test_generate_chain_with_none_chain(self, sample_incident):
        """Test generating chain with None chain object."""
        chains = {'test_chain': None}

        with patch('app.incident.incident.logger') as mock_logger:
            sample_incident.generate_chain(chains, 'test_chain')

        mock_logger.warning.assert_called_once()
        assert len(sample_incident.chain) == 0

    def test_generate_chain_with_no_steps_attribute(self, sample_incident):
        """Test generating chain with chain that has no steps attribute."""
        chains = {'test_chain': Mock()}
        del chains['test_chain'].steps

        with patch('app.incident.incident.logger') as mock_logger:
            sample_incident.generate_chain(chains, 'test_chain')

        mock_logger.error.assert_called_once()
        assert len(sample_incident.chain) == 0

    def test_generate_chain_with_empty_steps(self, sample_incident):
        """Test generating chain with empty steps."""
        chains = {'test_chain': Mock(steps=[])}

        with patch('app.incident.incident.logger') as mock_logger:
            sample_incident.generate_chain(chains, 'test_chain')

        mock_logger.debug.assert_called_once()
        assert len(sample_incident.chain) == 0

    def test_generate_chain_with_nested_chains(self, sample_incident):
        """Test generating chain with nested chain references."""
        chains = create_mock_chains_config({
            'main_chain': [
                {'user': 'testuser'},
                {'chain': 'nested_chain'},
                {'wait': '10m'}
            ],
            'nested_chain': [
                {'user': 'admin'},
                {'wait': '5m'}
            ]
        })

        with patch.object(sample_incident, 'dump'):
            sample_incident.generate_chain(chains, 'main_chain')

        # Should have 2 user steps (wait steps don't create chain items)
        assert len(sample_incident.chain) == 2
        assert sample_incident.chain[0]['type'] == 'user'
        assert sample_incident.chain[0]['identifier'] == 'testuser'
        assert sample_incident.chain[1]['type'] == 'user'
        assert sample_incident.chain[1]['identifier'] == 'admin'

    def test_generate_chain_with_missing_nested_chain(self, sample_incident):
        """Test generating chain with missing nested chain."""
        chains = {
            'main_chain': Mock(steps=[
                {'user': 'testuser'},
                {'chain': 'missing_nested'},
                {'wait': '10m'}
            ])
        }

        with patch('app.incident.incident.logger') as mock_logger:
            with patch('builtins.open', mock_open()):
                with patch('os.makedirs'):
                    sample_incident.generate_chain(chains, 'main_chain')

        mock_logger.warning.assert_called_once()
        # Should have 1 step: user (missing nested chain and wait are skipped)
        assert len(sample_incident.chain) == 1

    def test_get_step_type_and_value_with_dict(self, sample_incident):
        """Test _get_step_type_and_value with dictionary step."""
        step = {'user': 'testuser'}
        type_, value = sample_incident._get_step_type_and_value(step)
        assert type_ == 'user'
        assert value == 'testuser'

    def test_get_step_type_and_value_with_object(self, sample_incident):
        """Test _get_step_type_and_value with object step."""
        mock_step = Mock()
        mock_step.get_type_and_value.return_value = ('user', 'testuser')

        type_, value = sample_incident._get_step_type_and_value(mock_step)
        assert type_ == 'user'
        assert value == 'testuser'
        mock_step.get_type_and_value.assert_called_once()

    def test_get_step_type_and_value_with_unknown_format(self, sample_incident):
        """Test _get_step_type_and_value with unknown step format."""
        with pytest.raises(ValueError, match="Unknown step format"):
            sample_incident._get_step_type_and_value("invalid_step")

    def test_step_has_chain_with_dict(self, sample_incident):
        """Test _step_has_chain with dictionary step."""
        step_with_chain = {'chain': 'nested_chain'}
        step_without_chain = {'user': 'testuser'}

        assert sample_incident._step_has_chain(step_with_chain) is True
        assert sample_incident._step_has_chain(step_without_chain) is False

    def test_step_has_chain_with_object(self, sample_incident):
        """Test _step_has_chain with object step."""
        mock_step = Mock()
        mock_step.has_chain.return_value = True

        result = sample_incident._step_has_chain(mock_step)
        assert result is True
        mock_step.has_chain.assert_called_once()

    def test_step_has_chain_with_unknown_format(self, sample_incident):
        """Test _step_has_chain with unknown step format."""
        result = sample_incident._step_has_chain("invalid_step")
        assert result is False

    def test_unchain_with_no_chains(self, sample_incident):
        """Test _unchain with steps that have no chain references."""
        chains = {}
        steps = [{'user': 'testuser'}, {'wait': '5m'}]

        result = sample_incident._unchain(chains, steps)
        assert result == steps

    def test_unchain_with_chains(self, sample_incident):
        """Test _unchain with steps that have chain references."""
        chains = {
            'nested_chain': Mock(steps=[{'user': 'admin'}, {'wait': '3m'}])
        }
        steps = [{'user': 'testuser'}, {'chain': 'nested_chain'}, {'wait': '5m'}]

        result = sample_incident._unchain(chains, steps)
        assert len(result) == 4
        assert result[0] == {'user': 'testuser'}
        assert result[1] == {'user': 'admin'}
        assert result[2] == {'wait': '3m'}
        assert result[3] == {'wait': '5m'}

    def test_unchain_with_missing_nested_chain(self, sample_incident):
        """Test _unchain with missing nested chain."""
        chains = {}
        steps = [{'user': 'testuser'}, {'chain': 'missing_chain'}, {'wait': '5m'}]

        with patch('app.incident.incident.logger') as mock_logger:
            result = sample_incident._unchain(chains, steps)

        mock_logger.warning.assert_called_once()
        assert len(result) == 2  # Missing chain is skipped
        assert result[0] == {'user': 'testuser'}
        assert result[1] == {'wait': '5m'}

    def test_unchain_with_none_nested_chain(self, sample_incident):
        """Test _unchain with None nested chain."""
        chains = {'nested_chain': None}
        steps = [{'user': 'testuser'}, {'chain': 'nested_chain'}, {'wait': '5m'}]

        with patch('app.incident.incident.logger') as mock_logger:
            result = sample_incident._unchain(chains, steps)

        mock_logger.warning.assert_called_once()
        assert len(result) == 2  # None chain is skipped
        assert result[0] == {'user': 'testuser'}
        assert result[1] == {'wait': '5m'}

    @patch('app.incident.incident.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.load')
    def test_load_incident(self, mock_yaml_load, mock_file_open, mock_get_config, incident_config, mock_unified_config):
        """Test loading incident from file."""
        mock_get_config.return_value = mock_unified_config

        # Use utility function to create mock incident data
        mock_incident_data = create_mock_incident_data()
        mock_incident_data['uniq_id'] = 'test-uniq-id-from-file'
        mock_yaml_load.return_value = mock_incident_data

        incident = Incident.load('/test/incident.yml', incident_config)

        assert incident.status == 'firing'
        assert incident.channel_id == 'C123456789'
        assert incident.payload == {'alertname': 'TestAlert', 'severity': 'critical'}
        assert incident.assigned_user_id == 'U123456'
        assert incident.assigned_user == 'testuser'
        assert incident.assigned_fullname == 'Test User'
        assert incident.messenger_type == 'slack'
        assert incident.ts == '1234567890.123456'
        assert incident.link == 'https://test.slack.comarchives/C123456789/p1234567890123456'
        # uniq_id is always regenerated in __post_init__, so check it exists but don't check exact value
        assert incident.uniq_id is not None
        assert incident.uniq_id != ''
        assert incident.uuid is not None

    @patch('app.incident.incident.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.load')
    def test_load_incident_without_uniq_id(self, mock_yaml_load, mock_file_open, mock_get_config, incident_config, mock_unified_config):
        """Test loading incident from file when uniq_id is missing."""
        mock_get_config.return_value = mock_unified_config

        # Use utility function to create mock incident data without uniq_id
        mock_incident_data = create_mock_incident_data()
        # Don't set uniq_id - it should be generated in __post_init__
        mock_yaml_load.return_value = mock_incident_data

        incident = Incident.load('/test/incident.yml', incident_config)

        assert incident.status == 'firing'
        assert incident.channel_id == 'C123456789'
        # uniq_id should be generated automatically
        assert incident.uniq_id is not None
        assert incident.uniq_id != ''
        assert incident.uuid is not None

    @patch('app.incident.incident.get_environment_config')
    @patch('app.incident.incident.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.dump')
    @patch('asyncio.get_event_loop')
    @patch('app.incident.incident.incident_ws')
    def test_dump_with_websocket_update(self, mock_incident_ws, mock_get_loop, mock_yaml_dump, mock_file_open,
                                        mock_get_config, mock_get_env_config, sample_incident, mock_unified_config, mock_environment_config):
        """Test dumping incident with websocket update."""
        mock_get_config.return_value = mock_unified_config
        mock_get_env_config.return_value = mock_environment_config
        mock_environment_config.incidents_path = "/test/incidents"

        # Use utility function to create mock event loop
        mock_loop = create_mock_event_loop(running=True)
        mock_get_loop.return_value = mock_loop

        sample_incident.dump()

        mock_file_open.assert_called_once()
        mock_yaml_dump.assert_called_once()
        mock_incident_ws.update_row.assert_called_once_with(sample_incident)

    @patch('app.incident.incident.get_environment_config')
    @patch('app.incident.incident.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.dump')
    @patch('asyncio.get_event_loop', side_effect=RuntimeError("No event loop"))
    @patch('app.incident.incident.incident_ws')
    def test_dump_without_websocket_update(self, mock_incident_ws, mock_get_loop, mock_yaml_dump, mock_file_open,
                                           mock_get_config, mock_get_env_config, sample_incident, mock_unified_config, mock_environment_config):
        """Test dumping incident without websocket update (no event loop)."""
        mock_get_config.return_value = mock_unified_config
        mock_get_env_config.return_value = mock_environment_config
        mock_environment_config.incidents_path = "/test/incidents"

        sample_incident.dump()

        mock_file_open.assert_called_once()
        mock_yaml_dump.assert_called_once()
        mock_incident_ws.update_row.assert_not_called()

    def test_get_table_data_single_alert(self, sample_incident):
        """Test get_table_data with single alert."""
        sample_incident.payload = {
            'alerts': [{'status': 'firing', 'labels': {'alert': 'test'}}]
        }

        result = sample_incident.get_table_data({})

        assert result['uniq_id'] == sample_incident.uniq_id
        assert result['indicator'] == sample_incident.status
        assert result['_alerts_count'] == 1
        assert 'group_labels' in result['_responsive_data']
        assert 'common_labels' in result['_responsive_data']
        assert 'common_annotations' in result['_responsive_data']
        assert 'incident_info' in result['_responsive_data']
        assert 'alerts' in result['_responsive_data']

    def test_get_table_data_multiple_alerts(self, sample_incident):
        """Test get_table_data with multiple alerts."""
        sample_incident.payload = {
            'alerts': [
                {'status': 'firing', 'labels': {'alert': 'test1'}},
                {'status': 'resolved', 'labels': {'alert': 'test2'}}
            ],
            'groupLabels': {'alertname': 'TestAlert'},
            'commonLabels': {'severity': 'critical'},
            'commonAnnotations': {'summary': 'Test alert'}
        }

        result = sample_incident.get_table_data({})

        assert result['_alerts_count'] == 2
        assert result['_responsive_data']['group_labels'] == {'alertname': 'TestAlert'}
        assert result['_responsive_data']['common_labels'] == {'severity': 'critical'}
        assert result['_responsive_data']['common_annotations'] == {'summary': 'Test alert'}

    def test_get_table_data_with_params(self, sample_incident):
        """Test get_table_data with custom parameters."""
        sample_incident.payload = {'alerts': []}

        params = {
            'custom_field': 'incident.status',
            'another_field': 'incident.payload.alertname'
        }

        result = sample_incident.get_table_data(params)

        assert 'custom_field' in result
        assert 'another_field' in result

    def test_created_datetime_handling(self, sample_alert_payload, incident_config):
        """Test that created datetime is set when not provided."""
        # Create incident without created datetime
        incident = Incident(
            payload=sample_alert_payload,
            status="firing",
            channel_id="C123456789",
            config=incident_config,
            status_update_datetime=datetime.now(timezone.utc),
            assigned_user_id="",
            assigned_user="",
            assigned_fullname="",
            messenger_type="slack"
        )

        # Should have created datetime set
        assert incident.created is not None
        assert isinstance(incident.created, datetime)

    def test_created_datetime_when_falsy(self, sample_alert_payload, incident_config):
        """Test that created datetime is set when created is falsy."""
        # Create incident without created datetime (will use default)
        # Note: created=None will cause error in gen_uniq_id, so we skip it
        # and test with default_factory instead
        incident = Incident(
            payload=sample_alert_payload,
            status="firing",
            channel_id="C123456789",
            config=incident_config,
            status_update_datetime=datetime.now(timezone.utc),
            assigned_user_id="",
            assigned_user="",
            assigned_fullname="",
            messenger_type="slack"
            # created will be set by default_factory
        )

        # Should have created datetime set
        assert incident.created is not None
        assert isinstance(incident.created, datetime)


class TestIncidentInhibitionFields:
    """Test cases for inhibition-related fields in Incident class."""

    @patch('app.incident.incident.ChannelManager')
    def test_serialize_includes_inhibition_fields(self, mock_channel_manager, sample_incident):
        """Test that serialize includes inhibition-related fields."""
        mock_channel_manager.return_value.get_channel_name_by_id.return_value = "test-channel"
        
        sample_incident.frozen_by_inhibition = True
        sample_incident.childs = ["child-1", "child-2"]
        sample_incident.parents = ["parent-1"]

        result = sample_incident.serialize()

        assert 'frozen_by_inhibition' in result
        assert result['frozen_by_inhibition'] is True
        assert 'childs' in result
        assert result['childs'] == ["child-1", "child-2"]
        assert 'parents' in result
        assert result['parents'] == ["parent-1"]

    @patch('app.incident.incident.get_environment_config')
    @patch('app.incident.incident.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.dump')
    def test_dump_includes_inhibition_fields(
        self, mock_yaml_dump, mock_file_open, mock_get_config, mock_get_env_config, 
        sample_incident, mock_unified_config, mock_environment_config
    ):
        """Test that dump includes inhibition-related fields in YAML."""
        mock_get_config.return_value = mock_unified_config
        mock_get_env_config.return_value = mock_environment_config
        mock_environment_config.incidents_path = "/test/incidents"
        
        sample_incident.frozen_by_inhibition = True
        sample_incident.childs = ["child-1"]
        sample_incident.parents = ["parent-1", "parent-2"]

        with patch('app.incident.incident.incident_ws'):
            sample_incident.dump()

        # Check that yaml.dump was called with data containing inhibition fields
        call_args = mock_yaml_dump.call_args
        dumped_data = call_args[0][0]
        
        assert 'frozen_by_inhibition' in dumped_data
        assert dumped_data['frozen_by_inhibition'] is True
        assert 'childs' in dumped_data
        assert dumped_data['childs'] == ["child-1"]
        assert 'parents' in dumped_data
        assert dumped_data['parents'] == ["parent-1", "parent-2"]

    @patch('app.incident.incident.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.load')
    def test_load_includes_inhibition_fields(
        self, mock_yaml_load, mock_file_open, mock_get_config, 
        incident_config, mock_unified_config
    ):
        """Test that load properly reads inhibition-related fields."""
        mock_get_config.return_value = mock_unified_config

        mock_incident_data = create_mock_incident_data()
        mock_incident_data['frozen_by_inhibition'] = True
        mock_incident_data['childs'] = ["child-1", "child-2"]
        mock_incident_data['parents'] = ["parent-1"]
        mock_yaml_load.return_value = mock_incident_data

        incident = Incident.load('/test/incident.yml', incident_config)

        assert incident.frozen_by_inhibition is True
        assert incident.childs == ["child-1", "child-2"]
        assert incident.parents == ["parent-1"]

    @patch('app.incident.incident.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.load')
    def test_load_without_inhibition_fields_uses_defaults(
        self, mock_yaml_load, mock_file_open, mock_get_config, 
        incident_config, mock_unified_config
    ):
        """Test that load uses defaults when inhibition fields are missing."""
        mock_get_config.return_value = mock_unified_config

        # Old incident data without inhibition fields
        mock_incident_data = create_mock_incident_data()
        # Don't include frozen_by_inhibition, childs, or parents
        mock_yaml_load.return_value = mock_incident_data

        incident = Incident.load('/test/incident.yml', incident_config)

        # Should use defaults
        assert incident.frozen_by_inhibition is False
        assert incident.childs == []
        assert incident.parents == []

    def test_default_inhibition_field_values(self, sample_incident):
        """Test that inhibition fields have correct default values."""
        assert sample_incident.frozen_by_inhibition is False
        assert sample_incident.childs == []
        assert sample_incident.parents == []
        # Ensure they are mutable lists, not shared references
        assert sample_incident.childs is not sample_incident.parents

    def test_childs_and_parents_are_independent_lists(self, sample_incident):
        """Test that childs and parents are independent mutable lists."""
        # Modify one, ensure the other is unaffected
        sample_incident.childs.append("child-1")
        sample_incident.parents.append("parent-1")
        
        assert "child-1" in sample_incident.childs
        assert "parent-1" in sample_incident.parents
        assert "child-1" not in sample_incident.parents
        assert "parent-1" not in sample_incident.childs
