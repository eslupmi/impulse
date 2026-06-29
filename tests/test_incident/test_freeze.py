"""
Unit tests for incident freeze functionality.

This module tests the freeze/unfreeze functionality added to the Incident class,
including freezing incidents, automatic unfreezing, and freeze state checks.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.incident.incident import Incident, IncidentConfig, remove_freeze_source
from app.incident.freeze import FreezeSource
from tests.utils import create_alert_payload

INHIBITION_SOURCE_PARENT = "source-uniq-id"


def _apply_inhibition_freeze(incident: Incident):
    """Mirror production: source uniq_id in parents, then freeze_by_inhibition."""
    if INHIBITION_SOURCE_PARENT not in incident.parents:
        incident.parents.append(INHIBITION_SOURCE_PARENT)
    incident.freeze_by_inhibition()


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
        assert sample_incident.frozen_by_inhibition is False
        assert sample_incident.is_frozen() is False

    def test_unfrozen_incident_shows_actual_status(self, sample_incident):
        """Test that unfrozen incidents show their actual status."""
        table_data = sample_incident.get_table_data({})

        assert table_data['indicator'] == 'firing'
        assert table_data['_is_frozen'] is False

    def test_can_manual_unfreeze_manual_time_freeze(self, sample_incident):
        until = datetime.now(timezone.utc) + timedelta(hours=1)
        user = Mock(id="u1", username="alice", name="Alice")
        with patch.object(sample_incident, "dump"):
            sample_incident.freeze(until, user, FreezeSource.TIME)
        assert sample_incident.can_manual_unfreeze() is True

    def test_can_manual_unfreeze_false_for_maintenance(self, sample_incident):
        until = datetime.now(timezone.utc) + timedelta(hours=1)
        with patch.object(sample_incident, "dump"):
            sample_incident.set_maintenance_parent()
            sample_incident.freeze(until, user=None, source=FreezeSource.MAINTENANCE)
        assert sample_incident.can_manual_unfreeze() is False

    def test_can_manual_unfreeze_false_without_frozen_until(self, sample_incident):
        with patch.object(sample_incident, "dump"):
            sample_incident.set_maintenance_parent()
        assert sample_incident.can_manual_unfreeze() is False

    @pytest.mark.asyncio
    async def test_parent_unfreeze_restores_after_last_parent_already_removed(self, sample_incident):
        """Inhibition cleanup removes the parent first, then calls this to restore queues."""
        assert sample_incident.is_frozen() is False
        queue = Mock()

        with patch("app.incident.incident.sync_after_freeze_change", new_callable=AsyncMock) as sync_after_change:
            await remove_freeze_source(
                sample_incident,
                queue,
                source=FreezeSource.PARENT,
            )

        sync_after_change.assert_awaited_once_with(
            sample_incident,
            queue,
            "firing",
        )

class TestIncidentInhibitionFreeze:
    """Test cases for inhibition-based freeze functionality."""

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

    def test_incident_not_frozen_by_inhibition_by_default(self, sample_incident):
        """Test that incidents are not frozen by inhibition by default."""
        assert sample_incident.frozen_by_inhibition is False
        assert sample_incident.frozen_by_maintenance is False
        assert sample_incident.parents == []
        assert sample_incident.childs == []

    def test_freeze_by_inhibition(self, sample_incident):
        """Test freezing an incident by inhibition."""
        with patch.object(sample_incident, 'dump'):
            _apply_inhibition_freeze(sample_incident)

        assert sample_incident.frozen_by_inhibition is True
        assert sample_incident.is_frozen() is True

    def test_freeze_by_inhibition_does_not_affect_chain_enabled(self, sample_incident):
        """Test that freeze_by_inhibition does not change chain_enabled."""
        sample_incident.chain_enabled = True
        
        with patch.object(sample_incident, 'dump'):
            _apply_inhibition_freeze(sample_incident)

        # chain_enabled should remain unchanged
        assert sample_incident.chain_enabled is True
        assert sample_incident.frozen_by_inhibition is True

    def test_freeze_by_inhibition_persists_to_file(self, sample_incident):
        """Test that freeze_by_inhibition calls dump to persist state."""
        with patch.object(sample_incident, 'dump') as mock_dump:
            _apply_inhibition_freeze(sample_incident)
            mock_dump.assert_called_once()

    def test_unfreeze_clears_inhibition_freeze(self, sample_incident):
        """Test that unfreeze clears the inhibition freeze."""
        with patch.object(sample_incident, 'dump'):
            _apply_inhibition_freeze(sample_incident)
            assert sample_incident.frozen_by_inhibition is True
            
            sample_incident.unfreeze()
            
            assert sample_incident.frozen_by_inhibition is False
            assert sample_incident.frozen_by_maintenance is False
            assert sample_incident.is_frozen() is False

    def test_unfreeze_from_inhibition_does_not_affect_chain_enabled(self, sample_incident):
        """Test that unfreezing from inhibition does not change chain_enabled."""
        sample_incident.chain_enabled = True
        
        with patch.object(sample_incident, 'dump'):
            _apply_inhibition_freeze(sample_incident)
            assert sample_incident.chain_enabled is True  # unchanged
            
            sample_incident.unfreeze()
            
            # chain_enabled should remain True (inhibition unfreeze doesn't touch it)
            assert sample_incident.chain_enabled is True

    def test_is_frozen_with_inhibition_only(self, sample_incident):
        """Test is_frozen returns True when inhibition parent is recorded."""
        with patch.object(sample_incident, 'dump'):
            _apply_inhibition_freeze(sample_incident)
        
        assert sample_incident.frozen_until is None
        assert sample_incident.frozen_by_inhibition is True
        assert sample_incident.is_frozen() is True
        assert sample_incident.can_manual_unfreeze() is False
        assert sample_incident.can_manual_unfreeze() is False

    def test_parents_and_childs_lists(self, sample_incident):
        """Test that parents and childs lists can be modified."""
        sample_incident.parents.append("source-1")
        sample_incident.parents.append("source-2")
        sample_incident.childs.append("target-1")
        
        assert "source-1" in sample_incident.parents
        assert "source-2" in sample_incident.parents
        assert "target-1" in sample_incident.childs
        assert len(sample_incident.parents) == 2
        assert len(sample_incident.childs) == 1

    def test_freeze_by_inhibition_does_not_set_assignee(self, sample_incident):
        """Test that freeze_by_inhibition does not modify assignee."""
        original_user_id = sample_incident.assigned_user_id
        original_fullname = sample_incident.assigned_fullname
        
        with patch.object(sample_incident, 'dump'):
            _apply_inhibition_freeze(sample_incident)
        
        assert sample_incident.assigned_user_id == original_user_id
        assert sample_incident.assigned_fullname == original_fullname

    def test_freeze_by_inhibition_does_not_set_frozen_until(self, sample_incident):
        """Test that freeze_by_inhibition does not set frozen_until."""
        with patch.object(sample_incident, 'dump'):
            _apply_inhibition_freeze(sample_incident)
        
        assert sample_incident.frozen_until is None

    def test_inhibition_frozen_incident_shows_frozen_in_table_data(self, sample_incident):
        """Test that inhibition-frozen incidents show frozen status in table data."""
        with patch.object(sample_incident, 'dump'):
            _apply_inhibition_freeze(sample_incident)

        table_data = sample_incident.get_table_data({})

        assert table_data['indicator'] == 'frozen'
        assert table_data['_is_frozen'] is True
        # frozen_until should still be None
        assert table_data['_responsive_data']['incident_info']['frozen_until'] is None
