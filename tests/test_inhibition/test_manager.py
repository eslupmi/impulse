"""
Unit tests for InhibitionManager class.

Tests the inhibition management logic including processing incidents,
handling resolved/closed incidents, and maintaining parent/child relationships.
"""
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch

import pytest

from app.inhibition.manager import InhibitionManager
from app.config.validation import InhibitRule
from tests.utils import create_alert_payload, create_mock_queue, create_mock_application


class TestInhibitionManager:
    """Test cases for InhibitionManager class."""

    @pytest.fixture
    def mock_queue(self):
        """Create mock queue."""
        queue = create_mock_queue()
        queue.put_first = AsyncMock()
        return queue

    @pytest.fixture
    def mock_application(self):
        """Create mock application."""
        app = create_mock_application()
        app.update_thread = AsyncMock()
        app.update_incident_message = AsyncMock()
        app.body_template = Mock()
        app.body_template.form_message = Mock(return_value="body")
        app.header_template = Mock()
        app.header_template.form_message = Mock(return_value="header")
        app.status_icons_template = Mock()
        app.status_icons_template.form_message = Mock(return_value="icons")
        return app

    @pytest.fixture
    def mock_incidents(self):
        """Create mock incidents collection."""
        incidents = Mock()
        incidents.uniq_ids = {}
        incidents.active_map = {}
        return incidents

    @pytest.fixture
    def sample_inhibit_rule(self):
        """Create a sample InhibitRule config object."""
        rule = Mock(spec=InhibitRule)
        rule.source_matchers = ['severity = "critical"']
        rule.target_matchers = ['severity = "warning"']
        rule.equal = ['service']
        return rule

    @pytest.fixture
    def inhibition_manager(self, mock_queue, mock_application, mock_incidents, sample_inhibit_rule):
        """Create InhibitionManager instance with one rule."""
        return InhibitionManager(
            rules=[sample_inhibit_rule],
            incidents=mock_incidents,
            application=mock_application,
            queue=mock_queue
        )

    @pytest.fixture
    def empty_inhibition_manager(self, mock_queue, mock_application, mock_incidents):
        """Create InhibitionManager instance with no rules."""
        return InhibitionManager(
            rules=[],
            incidents=mock_incidents,
            application=mock_application,
            queue=mock_queue
        )

    def _create_mock_incident(self, uniq_id, severity, service, status="firing", 
                              ts="123456.789", parents=None, childs=None,
                              frozen_by_inhibition=False):
        """Create a mock incident for testing."""
        payload = create_alert_payload(severity=severity, service=service)
        
        incident = Mock()
        incident.uniq_id = uniq_id
        incident.uuid = f"uuid-{uniq_id}"
        incident.payload = payload
        incident.status = status
        incident.ts = ts
        incident.channel_id = "C123456789"
        incident.chain_enabled = True
        incident.frozen_until = None
        incident.task_link = ""
        incident.parents = parents if parents is not None else []
        incident.childs = childs if childs is not None else []
        incident.frozen_by_inhibition = frozen_by_inhibition
        incident.is_frozen = Mock(return_value=frozen_by_inhibition)
        incident.freeze_by_inhibition = Mock()
        incident.dump = Mock()
        return incident

    # Initialization Tests

    def test_initialization(self, inhibition_manager):
        """Test InhibitionManager initialization."""
        assert len(inhibition_manager.rules) == 1
        assert 0 in inhibition_manager.sources
        assert 0 in inhibition_manager.targets
        assert len(inhibition_manager.sources[0]) == 0
        assert len(inhibition_manager.targets[0]) == 0

    def test_initialization_empty_rules(self, empty_inhibition_manager):
        """Test InhibitionManager initialization with no rules."""
        assert len(empty_inhibition_manager.rules) == 0
        assert len(empty_inhibition_manager.sources) == 0
        assert len(empty_inhibition_manager.targets) == 0

    def test_initialization_multiple_rules(self, mock_queue, mock_application, mock_incidents):
        """Test InhibitionManager initialization with multiple rules."""
        rule1 = Mock(spec=InhibitRule)
        rule1.source_matchers = ['severity = "critical"']
        rule1.target_matchers = ['severity = "warning"']
        rule1.equal = ['service']
        
        rule2 = Mock(spec=InhibitRule)
        rule2.source_matchers = ['alertname = "HighPriority"']
        rule2.target_matchers = ['alertname = "LowPriority"']
        rule2.equal = []
        
        manager = InhibitionManager(
            rules=[rule1, rule2],
            incidents=mock_incidents,
            application=mock_application,
            queue=mock_queue
        )
        
        assert len(manager.rules) == 2
        assert 0 in manager.sources and 1 in manager.sources
        assert 0 in manager.targets and 1 in manager.targets

    # Process Incident Tests

    @pytest.mark.asyncio
    async def test_process_incident_no_rules(self, empty_inhibition_manager):
        """Test process_incident with no rules does nothing."""
        incident = self._create_mock_incident("inc-1", "critical", "api")
        
        await empty_inhibition_manager.process_incident(incident)
        
        # No rules means no processing
        assert len(empty_inhibition_manager.sources) == 0

    @pytest.mark.asyncio
    async def test_process_incident_adds_source(self, inhibition_manager, mock_incidents):
        """Test that source incident is added to sources set."""
        incident = self._create_mock_incident("source-1", "critical", "api")
        mock_incidents.uniq_ids = {"source-1": incident}
        
        await inhibition_manager.process_incident(incident)
        
        assert "source-1" in inhibition_manager.sources[0]

    @pytest.mark.asyncio
    async def test_process_incident_adds_target(self, inhibition_manager, mock_incidents):
        """Test that target incident is added to targets set."""
        incident = self._create_mock_incident("target-1", "warning", "api")
        mock_incidents.uniq_ids = {"target-1": incident}
        
        await inhibition_manager.process_incident(incident)
        
        assert "target-1" in inhibition_manager.targets[0]

    @pytest.mark.asyncio
    async def test_process_incident_neither_source_nor_target(self, inhibition_manager, mock_incidents):
        """Test incident that matches neither source nor target."""
        incident = self._create_mock_incident("other-1", "info", "api")
        mock_incidents.uniq_ids = {"other-1": incident}
        
        await inhibition_manager.process_incident(incident)
        
        assert "other-1" not in inhibition_manager.sources[0]
        assert "other-1" not in inhibition_manager.targets[0]


    @pytest.mark.asyncio
    async def test_equal_labels_prevent_freeze(self, inhibition_manager, mock_incidents):
        """Test that mismatched equal labels prevent freezing."""
        source = self._create_mock_incident("source-1", "critical", "api")
        target = self._create_mock_incident("target-1", "warning", "web")  # Different service
        
        mock_incidents.uniq_ids = {"source-1": source, "target-1": target}
        inhibition_manager.sources[0].add("source-1")
        
        await inhibition_manager.process_incident(target)
        
        # Target should NOT be frozen (services don't match)
        target.freeze_by_inhibition.assert_not_called()

    @pytest.mark.asyncio
    async def test_incident_cannot_freeze_itself(self, inhibition_manager, mock_incidents):
        """Test that an incident cannot be both source and target for same rule."""
        # Create incident that matches both source and target
        rule = Mock(spec=InhibitRule)
        rule.source_matchers = ['service = "api"']
        rule.target_matchers = ['service = "api"']
        rule.equal = []
        
        manager = InhibitionManager(
            rules=[rule],
            incidents=mock_incidents,
            application=inhibition_manager.application,
            queue=inhibition_manager.queue
        )
        
        incident = self._create_mock_incident("inc-1", "critical", "api")
        mock_incidents.uniq_ids = {"inc-1": incident}
        
        await manager.process_incident(incident)
        
        # Should not freeze itself
        incident.freeze_by_inhibition.assert_not_called()
        # But should be in both sets
        assert "inc-1" in manager.sources[0]
        assert "inc-1" in manager.targets[0]


    # Handle Resolved Tests

    @pytest.mark.asyncio
    async def test_handle_resolved_no_rules(self, empty_inhibition_manager):
        """Test handle_resolved with no rules does nothing."""
        incident = self._create_mock_incident("inc-1", "critical", "api")
        
        await empty_inhibition_manager.handle_resolved(incident)
        # Should not raise


    @pytest.mark.asyncio
    async def test_handle_resolved_multiple_parents_no_unfreeze(
        self, inhibition_manager, mock_incidents, mock_queue
    ):
        """Test that target with multiple parents is not unfrozen when one resolves."""
        source1 = self._create_mock_incident(
            "source-1", "critical", "api",
            childs=["target-1"]
        )
        target = self._create_mock_incident(
            "target-1", "warning", "api",
            parents=["source-1", "source-2"],
            frozen_by_inhibition=True
        )
        
        mock_incidents.uniq_ids = {"source-1": source1, "target-1": target}
        inhibition_manager.sources[0].add("source-1")
        inhibition_manager.targets[0].add("target-1")
        
        await inhibition_manager.handle_resolved(source1)
        
        # Source should be removed from parents
        assert "source-1" not in target.parents
        assert "source-2" in target.parents
        # Unfreeze should NOT be scheduled (still has parents)
        mock_queue.put_first.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_resolved_non_source_incident(self, inhibition_manager, mock_incidents):
        """Test that resolving a non-source incident does nothing."""
        target = self._create_mock_incident("target-1", "warning", "api")
        
        mock_incidents.uniq_ids = {"target-1": target}
        inhibition_manager.targets[0].add("target-1")
        
        await inhibition_manager.handle_resolved(target)
        
        # Nothing should happen
        target.dump.assert_not_called()

    # Handle Closed Tests

    @pytest.mark.asyncio
    async def test_handle_closed_no_rules(self, empty_inhibition_manager):
        """Test handle_closed with no rules does nothing."""
        incident = self._create_mock_incident("inc-1", "critical", "api")
        
        await empty_inhibition_manager.handle_closed(incident)
        # Should not raise

    @pytest.mark.asyncio
    async def test_handle_closed_source_removed_from_set(
        self, inhibition_manager, mock_incidents
    ):
        """Test that closing a source removes it from sources set."""
        source = self._create_mock_incident("source-1", "critical", "api", childs=[])
        
        mock_incidents.uniq_ids = {"source-1": source}
        inhibition_manager.sources[0].add("source-1")
        
        await inhibition_manager.handle_closed(source)
        
        assert "source-1" not in inhibition_manager.sources[0]


    @pytest.mark.asyncio
    async def test_handle_closed_unfrozen_target_removed_from_set(
        self, inhibition_manager, mock_incidents
    ):
        """Test that closing an unfrozen target removes it from targets set."""
        target = self._create_mock_incident(
            "target-1", "warning", "api",
            frozen_by_inhibition=False
        )
        target.is_frozen = Mock(return_value=False)
        
        mock_incidents.uniq_ids = {"target-1": target}
        inhibition_manager.targets[0].add("target-1")
        
        await inhibition_manager.handle_closed(target)
        
        assert "target-1" not in inhibition_manager.targets[0]

    @pytest.mark.asyncio
    async def test_handle_closed_frozen_target_not_removed(
        self, inhibition_manager, mock_incidents
    ):
        """Test that closing a frozen target does not remove it from targets set."""
        target = self._create_mock_incident(
            "target-1", "warning", "api",
            parents=["source-1"],
            frozen_by_inhibition=True
        )
        target.is_frozen = Mock(return_value=True)
        
        mock_incidents.uniq_ids = {"target-1": target}
        inhibition_manager.targets[0].add("target-1")
        
        await inhibition_manager.handle_closed(target)
        
        # Frozen target should stay in targets set
        assert "target-1" in inhibition_manager.targets[0]

    # Restore From Incidents Tests

    def test_restore_from_incidents_no_rules(self, empty_inhibition_manager, mock_incidents):
        """Test restore_from_incidents with no rules does nothing."""
        incident = self._create_mock_incident("inc-1", "critical", "api")
        mock_incidents.active_map = {"uuid-inc-1": "inc-1"}
        mock_incidents.uniq_ids = {"inc-1": incident}
        
        empty_inhibition_manager.restore_from_incidents()
        # Should not raise

    def test_restore_from_incidents_adds_sources(self, inhibition_manager, mock_incidents):
        """Test that restore_from_incidents adds source incidents."""
        source = self._create_mock_incident("source-1", "critical", "api")
        mock_incidents.active_map = {"uuid-source-1": "source-1"}
        mock_incidents.uniq_ids = {"source-1": source}
        
        inhibition_manager.restore_from_incidents()
        
        assert "source-1" in inhibition_manager.sources[0]

    def test_restore_from_incidents_adds_targets(self, inhibition_manager, mock_incidents):
        """Test that restore_from_incidents adds target incidents."""
        target = self._create_mock_incident("target-1", "warning", "api")
        mock_incidents.active_map = {"uuid-target-1": "target-1"}
        mock_incidents.uniq_ids = {"target-1": target}
        
        inhibition_manager.restore_from_incidents()
        
        assert "target-1" in inhibition_manager.targets[0]

    def test_restore_from_incidents_all_statuses(self, inhibition_manager, mock_incidents):
        """Test that restore_from_incidents processes all statuses."""
        firing = self._create_mock_incident("firing-1", "critical", "api", status="firing")
        unknown = self._create_mock_incident("unknown-1", "critical", "api", status="unknown")
        resolved = self._create_mock_incident("resolved-1", "critical", "api", status="resolved")
        
        mock_incidents.active_map = {
            "uuid-firing-1": "firing-1",
            "uuid-unknown-1": "unknown-1",
            "uuid-resolved-1": "resolved-1",
        }
        mock_incidents.uniq_ids = {
            "firing-1": firing,
            "unknown-1": unknown,
            "resolved-1": resolved,
        }
        
        inhibition_manager.restore_from_incidents()
        
        # All should be added as sources
        assert "firing-1" in inhibition_manager.sources[0]
        assert "unknown-1" in inhibition_manager.sources[0]
        assert "resolved-1" in inhibition_manager.sources[0]

    @pytest.mark.asyncio
    async def test_apply_current_inhibition_no_rules(self, empty_inhibition_manager, mock_incidents):
        """Test apply_current_inhibition with no rules does nothing."""
        incident = self._create_mock_incident("inc-1", "critical", "api")
        mock_incidents.active_map = {"uuid-inc-1": "inc-1"}
        mock_incidents.uniq_ids = {"inc-1": incident}

        await empty_inhibition_manager.apply_current_inhibition()

        incident.freeze_by_inhibition.assert_not_called()
        empty_inhibition_manager.queue.delete_by_id.assert_not_awaited()
        empty_inhibition_manager.application.update_incident_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_apply_current_inhibition_processes_tracked_incidents(self, inhibition_manager, mock_incidents):
        """Test apply_current_inhibition processes incidents tracked by current rules."""
        source = self._create_mock_incident("source-1", "critical", "api")
        target = self._create_mock_incident("target-1", "warning", "api")
        mock_incidents.active_map = {"uuid-source-1": "source-1", "uuid-target-1": "target-1"}
        mock_incidents.uniq_ids = {"source-1": source, "target-1": target}
        inhibition_manager.restore_from_incidents()

        await inhibition_manager.apply_current_inhibition()

        assert "target-1" in source.childs
        assert "source-1" in target.parents
        target.freeze_by_inhibition.assert_called_once()
        inhibition_manager.queue.delete_by_id.assert_awaited_once_with(
            "target-1", delete_steps=True, delete_status=False
        )

    @pytest.mark.asyncio
    @patch("app.inhibition.manager.unfreeze_incident", new_callable=AsyncMock)
    async def test_apply_current_inhibition_cleans_untracked_state(
        self, mock_unfreeze_incident, inhibition_manager, mock_incidents
    ):
        """Test stale inhibition links are cleaned and stale frozen target is unfrozen."""
        async def _unfreeze_side_effect(incident, _application, _queue):
            incident.frozen_by_inhibition = False

        mock_unfreeze_incident.side_effect = _unfreeze_side_effect

        source = self._create_mock_incident("source-1", "critical", "api", childs=["target-1"])
        target = self._create_mock_incident(
            "target-1", "warning", "api", parents=["source-1"], frozen_by_inhibition=True
        )

        # No current rules match these incidents, but stale inhibition links exist.
        target.payload["commonLabels"]["severity"] = "info"
        mock_incidents.active_map = {"uuid-source-1": "source-1", "uuid-target-1": "target-1"}
        mock_incidents.uniq_ids = {"source-1": source, "target-1": target}
        inhibition_manager.restore_from_incidents()

        await inhibition_manager.apply_current_inhibition()

        target.freeze_by_inhibition.assert_not_called()
        assert source.childs == []
        assert target.parents == []
        mock_unfreeze_incident.assert_awaited_once_with(target, inhibition_manager.application, inhibition_manager.queue)
        inhibition_manager.application.update_incident_message.assert_awaited_once_with(target)

    @pytest.mark.asyncio
    @patch("app.inhibition.manager.unfreeze_incident", new_callable=AsyncMock)
    async def test_apply_current_inhibition_cleans_tracked_links_after_equal_change(
        self, mock_unfreeze_incident, inhibition_manager, mock_incidents
    ):
        """Test stale links are removed when incidents remain tracked but equal labels no longer match."""
        async def _unfreeze_side_effect(incident, _application, _queue):
            incident.frozen_by_inhibition = False

        mock_unfreeze_incident.side_effect = _unfreeze_side_effect

        source = self._create_mock_incident("source-1", "critical", "api", childs=["target-1"])
        target = self._create_mock_incident(
            "target-1", "warning", "api", parents=["source-1"], frozen_by_inhibition=True
        )
        target.payload["commonLabels"]["service"] = "web"

        mock_incidents.active_map = {"uuid-source-1": "source-1", "uuid-target-1": "target-1"}
        mock_incidents.uniq_ids = {"source-1": source, "target-1": target}
        inhibition_manager.restore_from_incidents()

        await inhibition_manager.apply_current_inhibition()

        assert source.childs == []
        assert target.parents == []
        target.freeze_by_inhibition.assert_not_called()
        mock_unfreeze_incident.assert_awaited_once_with(target, inhibition_manager.application, inhibition_manager.queue)

    @pytest.mark.asyncio
    @patch("app.inhibition.manager.unfreeze_incident", new_callable=AsyncMock)
    async def test_apply_current_inhibition_keeps_valid_existing_link(
        self, mock_unfreeze_incident, inhibition_manager, mock_incidents
    ):
        """Test existing parent-child link is preserved when still valid under current rules."""
        source = self._create_mock_incident("source-1", "critical", "api", childs=["target-1"])
        target = self._create_mock_incident(
            "target-1", "warning", "api", parents=["source-1"], frozen_by_inhibition=True
        )

        mock_incidents.active_map = {"uuid-source-1": "source-1", "uuid-target-1": "target-1"}
        mock_incidents.uniq_ids = {"source-1": source, "target-1": target}
        inhibition_manager.restore_from_incidents()

        await inhibition_manager.apply_current_inhibition()

        assert source.childs == ["target-1"]
        assert target.parents == ["source-1"]
        target.freeze_by_inhibition.assert_not_called()
        inhibition_manager.queue.delete_by_id.assert_not_awaited()
        mock_unfreeze_incident.assert_not_awaited()

    @pytest.mark.asyncio
    @patch("app.inhibition.manager.unfreeze_incident", new_callable=AsyncMock)
    async def test_apply_current_inhibition_keeps_link_if_any_rule_matches(
        self, mock_unfreeze_incident, mock_queue, mock_application, mock_incidents
    ):
        """Test link remains valid if at least one rule still matches equal labels."""
        rule_service = Mock(spec=InhibitRule)
        rule_service.source_matchers = ['severity = "critical"']
        rule_service.target_matchers = ['severity = "warning"']
        rule_service.equal = ['service']

        rule_cluster = Mock(spec=InhibitRule)
        rule_cluster.source_matchers = ['severity = "critical"']
        rule_cluster.target_matchers = ['severity = "warning"']
        rule_cluster.equal = ['cluster']

        manager = InhibitionManager(
            rules=[rule_service, rule_cluster],
            incidents=mock_incidents,
            application=mock_application,
            queue=mock_queue
        )

        source = self._create_mock_incident("source-1", "critical", "api", childs=["target-1"])
        target = self._create_mock_incident(
            "target-1", "warning", "api", parents=["source-1"], frozen_by_inhibition=True
        )
        target.payload["commonLabels"]["service"] = "web"
        source.payload["commonLabels"]["cluster"] = "prod"
        target.payload["commonLabels"]["cluster"] = "prod"

        mock_incidents.active_map = {"uuid-source-1": "source-1", "uuid-target-1": "target-1"}
        mock_incidents.uniq_ids = {"source-1": source, "target-1": target}
        manager.restore_from_incidents()

        await manager.apply_current_inhibition()

        assert source.childs == ["target-1"]
        assert target.parents == ["source-1"]
        target.freeze_by_inhibition.assert_not_called()
        mock_queue.delete_by_id.assert_not_awaited()
        mock_unfreeze_incident.assert_not_awaited()

    # Reload Rules Tests

    def test_reload_rules(self, inhibition_manager, mock_incidents):
        """Test reload_rules reinitializes rules and restores state."""
        # Add some state
        inhibition_manager.sources[0].add("old-source")
        inhibition_manager.targets[0].add("old-target")
        
        # Create new rule
        new_rule = Mock(spec=InhibitRule)
        new_rule.source_matchers = ['alertname = "NewAlert"']
        new_rule.target_matchers = ['alertname = "OldAlert"']
        new_rule.equal = []
        
        # Set up incident for restoration
        incident = self._create_mock_incident("new-inc", "critical", "api")
        incident.payload['commonLabels']['alertname'] = "NewAlert"
        mock_incidents.active_map = {"uuid-new-inc": "new-inc"}
        mock_incidents.uniq_ids = {"new-inc": incident}
        
        inhibition_manager.reload_rules([new_rule])
        
        # Old state should be cleared
        assert "old-source" not in inhibition_manager.sources.get(0, set())
        assert "old-target" not in inhibition_manager.targets.get(0, set())

    # Thread Update Tests

