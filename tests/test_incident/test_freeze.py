"""
Unit tests for incident freeze functionality.

This module tests the freeze/unfreeze functionality added to the Incident class,
including freezing incidents, automatic unfreezing, and freeze state checks.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch

import pytest

from app.incident.incident import Incident, IncidentConfig
from tests.utils import create_alert_payload


class TestIncidentFreeze:
    """Test cases for Incident freeze functionality."""

    @pytest.fixture
    def incident_config(self):
        """Create incident configuration for testing."""
        return IncidentConfig(
            application_type="slack",
            application_url="https://test.slack.com",
            application_team="test-team"
        )

    @pytest.fixture
    def sample_incident(self, incident_config):
        """Create a sample incident for testing."""
        payload = create_alert_payload(status="firing", alertname="TestAlert")
        return Incident(
            payload=payload,
            status="firing",
            channel_id="C123456789",
            config=incident_config,
            status_update_datetime=datetime.now(timezone.utc),
            assigned_user_id="",
            assigned_user="",
            assigned_fullname="",
            messenger_type="slack"
        )

    def test_incident_not_frozen_by_default(self, sample_incident):
        """Test that incidents are not frozen by default."""
        assert sample_incident.frozen_until is None
        assert sample_incident.is_frozen() is False

    def test_freeze_incident(self, sample_incident):
        """Test freezing an incident."""
        freeze_until = datetime.now(timezone.utc) + timedelta(hours=2)
        user_id = "U123456"
        user_fullname = "Test User"

        with patch.object(sample_incident, 'dump'):
            sample_incident.freeze(freeze_until, user_id, user_fullname)

        assert sample_incident.frozen_until == freeze_until
        assert sample_incident.assigned_user_id == user_id
        assert sample_incident.assigned_fullname == user_fullname
        assert sample_incident.chain_enabled is False
        assert sample_incident.is_frozen() is True

    def test_freeze_incident_without_fullname(self, sample_incident):
        """Test freezing an incident without providing user fullname."""
        freeze_until = datetime.now(timezone.utc) + timedelta(hours=1)
        user_id = "U123456"

        with patch.object(sample_incident, 'dump'):
            sample_incident.freeze(freeze_until, user_id)

        assert sample_incident.frozen_until == freeze_until
        assert sample_incident.assigned_user_id == user_id
        # Fullname should not be updated when not provided
        assert sample_incident.is_frozen() is True

    def test_unfreeze_incident(self, sample_incident):
        """Test unfreezing an incident."""
        # First freeze the incident
        freeze_until = datetime.now(timezone.utc) + timedelta(hours=1)
        with patch.object(sample_incident, 'dump'):
            sample_incident.freeze(freeze_until, "U123456", "Test User")

        # Verify it's frozen
        assert sample_incident.is_frozen() is True

        # Now unfreeze it
        with patch.object(sample_incident, 'dump'):
            sample_incident.unfreeze()

        assert sample_incident.frozen_until is None
        assert sample_incident.chain_enabled is True
        assert sample_incident.is_frozen() is False

    def test_freeze_disables_chains(self, sample_incident):
        """Test that freezing an incident disables chains."""
        # Enable chains first
        sample_incident.chain_enabled = True

        freeze_until = datetime.now(timezone.utc) + timedelta(hours=1)
        with patch.object(sample_incident, 'dump'):
            sample_incident.freeze(freeze_until, "U123456")

        assert sample_incident.chain_enabled is False

    def test_unfreeze_enables_chains(self, sample_incident):
        """Test that unfreezing an incident re-enables chains."""
        # Freeze the incident
        freeze_until = datetime.now(timezone.utc) + timedelta(hours=1)
        with patch.object(sample_incident, 'dump'):
            sample_incident.freeze(freeze_until, "U123456")
            assert sample_incident.chain_enabled is False

        # Unfreeze it
        with patch.object(sample_incident, 'dump'):
            sample_incident.unfreeze()

        assert sample_incident.chain_enabled is True

    def test_freeze_persists_to_file(self, sample_incident):
        """Test that freezing an incident calls dump to persist the state."""
        freeze_until = datetime.now(timezone.utc) + timedelta(hours=1)

        with patch.object(sample_incident, 'dump') as mock_dump:
            sample_incident.freeze(freeze_until, "U123456", "Test User")
            mock_dump.assert_called_once()

    def test_unfreeze_persists_to_file(self, sample_incident):
        """Test that unfreezing an incident calls dump to persist the state."""
        # First freeze
        freeze_until = datetime.now(timezone.utc) + timedelta(hours=1)
        with patch.object(sample_incident, 'dump'):
            sample_incident.freeze(freeze_until, "U123456")

        # Then unfreeze
        with patch.object(sample_incident, 'dump') as mock_dump:
            sample_incident.unfreeze()
            mock_dump.assert_called_once()

    def test_frozen_incident_in_get_table_data(self, sample_incident):
        """Test that frozen incidents show frozen status in table data."""
        freeze_until = datetime.now(timezone.utc) + timedelta(hours=1)
        with patch.object(sample_incident, 'dump'):
            sample_incident.freeze(freeze_until, "U123456")

        table_data = sample_incident.get_table_data({})

        assert table_data['indicator'] == 'frozen'
        assert table_data['_is_frozen'] is True
        assert table_data['_responsive_data']['incident_info']['is_frozen'] is True
        assert table_data['_responsive_data']['incident_info']['frozen_until'] is not None

    def test_unfrozen_incident_shows_actual_status(self, sample_incident):
        """Test that unfrozen incidents show their actual status."""
        table_data = sample_incident.get_table_data({})

        assert table_data['indicator'] == 'firing'
        assert table_data['_is_frozen'] is False
        assert table_data['_responsive_data']['incident_info']['is_frozen'] is False

    def test_freeze_with_past_datetime(self, sample_incident):
        """Test that incidents can be frozen with past datetime (edge case)."""
        # This tests the system's behavior when someone tries to freeze with a past time
        freeze_until = datetime.now(timezone.utc) - timedelta(hours=1)

        with patch.object(sample_incident, 'dump'):
            sample_incident.freeze(freeze_until, "U123456")

        # The incident should still be frozen, but should be automatically unfrozen
        # by the UnfreezeHandler when it processes the queue
        assert sample_incident.frozen_until == freeze_until
        assert sample_incident.is_frozen() is True

    def test_multiple_freeze_unfreeze_cycles(self, sample_incident):
        """Test multiple freeze/unfreeze cycles on the same incident."""
        with patch.object(sample_incident, 'dump'):
            # First cycle
            sample_incident.freeze(datetime.now(timezone.utc) + timedelta(hours=1), "U111")
            assert sample_incident.is_frozen() is True
            sample_incident.unfreeze()
            assert sample_incident.is_frozen() is False

            # Second cycle
            sample_incident.freeze(datetime.now(timezone.utc) + timedelta(hours=2), "U222")
            assert sample_incident.is_frozen() is True
            sample_incident.unfreeze()
            assert sample_incident.is_frozen() is False

    def test_freeze_preserves_incident_status(self, sample_incident):
        """Test that freezing an incident preserves its underlying status."""
        original_status = sample_incident.status

        freeze_until = datetime.now(timezone.utc) + timedelta(hours=1)
        with patch.object(sample_incident, 'dump'):
            sample_incident.freeze(freeze_until, "U123456")

        # Status should be preserved
        assert sample_incident.status == original_status
        # But display status should be 'frozen'
        table_data = sample_incident.get_table_data({})
        assert table_data['indicator'] == 'frozen'

    def test_unfreeze_preserves_incident_status(self, sample_incident):
        """Test that unfreezing an incident preserves its underlying status."""
        # Change status before freezing
        sample_incident.status = "unknown"

        freeze_until = datetime.now(timezone.utc) + timedelta(hours=1)
        with patch.object(sample_incident, 'dump'):
            sample_incident.freeze(freeze_until, "U123456")
            sample_incident.unfreeze()

        # Status should still be 'unknown'
        assert sample_incident.status == "unknown"

    def test_get_chain_when_frozen(self, sample_incident):
        """Test that get_chain returns empty list when frozen."""
        sample_incident.chain = [
            {'user': 'user1', 'done': False},
            {'user': 'user2', 'done': False}
        ]
        sample_incident.chain_enabled = True

        # Before freezing, chain should be returned
        assert len(sample_incident.get_chain()) == 2

        # After freezing, chain_enabled is False, so get_chain returns empty list
        freeze_until = datetime.now(timezone.utc) + timedelta(hours=1)
        with patch.object(sample_incident, 'dump'):
            sample_incident.freeze(freeze_until, "U123456")

        assert sample_incident.get_chain() == []

    def test_get_chain_after_unfreeze(self, sample_incident):
        """Test that get_chain returns chain after unfreezing."""
        sample_incident.chain = [
            {'user': 'user1', 'done': False},
            {'user': 'user2', 'done': False}
        ]

        # Freeze and unfreeze
        freeze_until = datetime.now(timezone.utc) + timedelta(hours=1)
        with patch.object(sample_incident, 'dump'):
            sample_incident.freeze(freeze_until, "U123456")
            sample_incident.unfreeze()

        # Chain should be available again
        assert len(sample_incident.get_chain()) == 2

    def test_freeze_updates_assigned_user(self, sample_incident):
        """Test that freeze assigns the user who froze the incident."""
        original_user_id = "U000000"
        sample_incident.assigned_user_id = original_user_id

        freeze_user_id = "U999999"
        freeze_until = datetime.now(timezone.utc) + timedelta(hours=1)

        with patch.object(sample_incident, 'dump'):
            sample_incident.freeze(freeze_until, freeze_user_id, "Freeze User")

        # User should be updated to the one who froze the incident
        assert sample_incident.assigned_user_id == freeze_user_id
        assert sample_incident.assigned_fullname == "Freeze User"
