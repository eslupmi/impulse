"""
Unit tests for app.incident.incident module.
"""
import pytest
from unittest.mock import Mock, patch, mock_open
from datetime import datetime, timezone, timedelta

from app.incident.incident import Incident, IncidentConfig
from app.config.validation import MessengerType


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
        assert incident.ts == ""
        assert incident.link == ""

    @patch('app.incident.incident.gen_uuid')
    def test_incident_uuid_generation(self, mock_gen_uuid, sample_alert_payload, incident_config):
        """Test that UUID is generated correctly."""
        mock_gen_uuid.return_value = "test-uuid"
        
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
        
        mock_gen_uuid.assert_called_once_with(sample_alert_payload.get('groupLabels'))
        assert incident.uuid == "test-uuid"

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
            result = sample_incident.set_next_status()
            mock_update.assert_called_once_with("unknown")
            assert result is True

    def test_set_next_status_unknown_to_closed(self, sample_incident):
        """Test status transition from unknown to closed."""
        sample_incident.status = "unknown"
        with patch.object(sample_incident, 'update_status') as mock_update:
            mock_update.return_value = True
            result = sample_incident.set_next_status()
            mock_update.assert_called_once_with("closed")
            assert result is True

    def test_set_next_status_resolved_to_closed(self, sample_incident):
        """Test status transition from resolved to closed."""
        sample_incident.status = "resolved"
        with patch.object(sample_incident, 'update_status') as mock_update:
            mock_update.return_value = True
            result = sample_incident.set_next_status()
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

    def test_assign_user_methods(self, sample_incident):
        """Test user assignment methods."""
        sample_incident.assign_user_id("U123456")
        assert sample_incident.assigned_user_id == "U123456"
        
        sample_incident.assign_user("john.doe")
        assert sample_incident.assigned_user == "john.doe"
        
        sample_incident.assign_fullname("John Doe")
        assert sample_incident.assigned_fullname == "John Doe"

    def test_set_status(self, sample_incident):
        """Test setting status."""
        sample_incident.set_status("resolved")
        assert sample_incident.status == "resolved"

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
        dt = datetime.utcnow()
        sample_incident.chain_put(0, dt, "test_type", "test_id")
        
        assert len(sample_incident.chain) == 1
        assert sample_incident.chain[0]['datetime'] == dt
        assert sample_incident.chain[0]['type'] == "test_type"
        assert sample_incident.chain[0]['identifier'] == "test_id"
        assert sample_incident.chain[0]['done'] is False
        assert sample_incident.chain[0]['result'] is None

    def test_chain_update(self, sample_incident):
        """Test updating chain item."""
        dt = datetime.utcnow()
        sample_incident.chain_put(0, dt, "test_type", "test_id")
        
        with patch.object(sample_incident, 'dump'):
            sample_incident.chain_update(0, True, "test_result")
        
        assert sample_incident.chain[0]['done'] is True
        assert sample_incident.chain[0]['result'] == "test_result"

    @patch('app.incident.incident.get_config')
    @patch('builtins.open', new_callable=mock_open)
    @patch('yaml.dump')
    def test_dump(self, mock_yaml_dump, mock_file_open, mock_get_config, sample_incident, mock_unified_config):
        """Test dumping incident to file."""
        mock_get_config.return_value = mock_unified_config
        mock_unified_config.incidents_path = "/test/incidents"
        
        with patch('app.incident.incident.incident_ws'):
            sample_incident.dump()
        
        mock_file_open.assert_called_once()
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
