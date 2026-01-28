"""
Unit tests for InhibitionRule class.

Tests the inhibition rule matching logic including source/target matching
and equal labels comparison.
"""
from unittest.mock import Mock

import pytest

from app.inhibition.rule import InhibitionRule
from tests.utils import create_alert_payload


class TestInhibitionRule:
    """Test cases for InhibitionRule class."""

    @pytest.fixture
    def critical_source_warning_target_rule(self):
        """Create a rule that matches critical as source, warning as target."""
        return InhibitionRule(
            source_matchers=['severity = "critical"'],
            target_matchers=['severity = "warning"'],
            equal_labels=['service', 'cluster']
        )

    @pytest.fixture
    def regex_rule(self):
        """Create a rule using regex matchers."""
        return InhibitionRule(
            source_matchers=['alertname =~ "Critical.*"'],
            target_matchers=['alertname =~ "Warning.*"'],
            equal_labels=['service']
        )

    @pytest.fixture
    def no_equal_labels_rule(self):
        """Create a rule without equal labels."""
        return InhibitionRule(
            source_matchers=['severity = "critical"'],
            target_matchers=['severity = "warning"'],
            equal_labels=[]
        )

    @pytest.fixture
    def multi_matcher_rule(self):
        """Create a rule with multiple matchers."""
        return InhibitionRule(
            source_matchers=['severity = "critical"', 'alertname = "HighPriority"'],
            target_matchers=['severity = "warning"', 'alertname = "LowPriority"'],
            equal_labels=['service']
        )

    def _create_incident_with_payload(self, payload):
        """Create a mock incident with the given payload."""
        incident = Mock()
        incident.payload = payload
        incident.uniq_id = f"test-{payload.get('commonLabels', {}).get('alertname', 'unknown')}"
        return incident

    def test_initialization(self, critical_source_warning_target_rule):
        """Test InhibitionRule initialization."""
        rule = critical_source_warning_target_rule
        
        assert len(rule.source_matchers) == 1
        assert len(rule.target_matchers) == 1
        assert rule.equal_labels == ['service', 'cluster']

    def test_initialization_with_none_equal_labels(self):
        """Test InhibitionRule initialization with None equal labels."""
        rule = InhibitionRule(
            source_matchers=['severity = "critical"'],
            target_matchers=['severity = "warning"'],
            equal_labels=None
        )
        assert rule.equal_labels == []

    def test_is_source_matches(self, critical_source_warning_target_rule):
        """Test is_source returns True for matching incident."""
        payload = create_alert_payload(severity="critical")
        incident = self._create_incident_with_payload(payload)
        
        assert critical_source_warning_target_rule.is_source(incident) is True

    def test_is_source_no_match(self, critical_source_warning_target_rule):
        """Test is_source returns False for non-matching incident."""
        payload = create_alert_payload(severity="warning")
        incident = self._create_incident_with_payload(payload)
        
        assert critical_source_warning_target_rule.is_source(incident) is False

    def test_is_target_matches(self, critical_source_warning_target_rule):
        """Test is_target returns True for matching incident."""
        payload = create_alert_payload(severity="warning")
        incident = self._create_incident_with_payload(payload)
        
        assert critical_source_warning_target_rule.is_target(incident) is True

    def test_is_target_no_match(self, critical_source_warning_target_rule):
        """Test is_target returns False for non-matching incident."""
        payload = create_alert_payload(severity="critical")
        incident = self._create_incident_with_payload(payload)
        
        assert critical_source_warning_target_rule.is_target(incident) is False

    def test_is_source_regex_matches(self, regex_rule):
        """Test is_source with regex matcher."""
        payload = create_alert_payload(alertname="CriticalDiskFull")
        incident = self._create_incident_with_payload(payload)
        
        assert regex_rule.is_source(incident) is True

    def test_is_source_regex_no_match(self, regex_rule):
        """Test is_source with regex matcher no match."""
        payload = create_alert_payload(alertname="WarningDiskLow")
        incident = self._create_incident_with_payload(payload)
        
        assert regex_rule.is_source(incident) is False

    def test_is_target_regex_matches(self, regex_rule):
        """Test is_target with regex matcher."""
        payload = create_alert_payload(alertname="WarningDiskLow")
        incident = self._create_incident_with_payload(payload)
        
        assert regex_rule.is_target(incident) is True

    def test_multi_matcher_all_must_match(self, multi_matcher_rule):
        """Test that all matchers must match for is_source."""
        # Only severity matches
        payload1 = create_alert_payload(severity="critical", alertname="OtherAlert")
        incident1 = self._create_incident_with_payload(payload1)
        assert multi_matcher_rule.is_source(incident1) is False
        
        # Only alertname matches
        payload2 = create_alert_payload(severity="warning", alertname="HighPriority")
        incident2 = self._create_incident_with_payload(payload2)
        assert multi_matcher_rule.is_source(incident2) is False
        
        # Both match
        payload3 = create_alert_payload(severity="critical", alertname="HighPriority")
        incident3 = self._create_incident_with_payload(payload3)
        assert multi_matcher_rule.is_source(incident3) is True

    def test_equal_labels_match_same_values(self, critical_source_warning_target_rule):
        """Test equal_labels_match when labels have same values."""
        source_payload = create_alert_payload(severity="critical", service="api")
        source_payload['commonLabels']['cluster'] = 'prod'
        source = self._create_incident_with_payload(source_payload)
        
        target_payload = create_alert_payload(severity="warning", service="api")
        target_payload['commonLabels']['cluster'] = 'prod'
        target = self._create_incident_with_payload(target_payload)
        
        assert critical_source_warning_target_rule.equal_labels_match(source, target) is True

    def test_equal_labels_match_different_values(self, critical_source_warning_target_rule):
        """Test equal_labels_match when labels have different values."""
        source_payload = create_alert_payload(severity="critical", service="api")
        source_payload['commonLabels']['cluster'] = 'prod'
        source = self._create_incident_with_payload(source_payload)
        
        target_payload = create_alert_payload(severity="warning", service="web")
        target_payload['commonLabels']['cluster'] = 'prod'
        target = self._create_incident_with_payload(target_payload)
        
        # service differs: api vs web
        assert critical_source_warning_target_rule.equal_labels_match(source, target) is False

    def test_equal_labels_match_missing_label(self, critical_source_warning_target_rule):
        """Test equal_labels_match when a label is missing."""
        source_payload = create_alert_payload(severity="critical", service="api")
        source_payload['commonLabels']['cluster'] = 'prod'
        source = self._create_incident_with_payload(source_payload)
        
        target_payload = create_alert_payload(severity="warning", service="api")
        # No cluster label
        target = self._create_incident_with_payload(target_payload)
        
        # cluster is missing in target (None != 'prod')
        assert critical_source_warning_target_rule.equal_labels_match(source, target) is False

    def test_equal_labels_match_both_missing_label(self, critical_source_warning_target_rule):
        """Test equal_labels_match when both are missing the label."""
        source_payload = create_alert_payload(severity="critical", service="api")
        source = self._create_incident_with_payload(source_payload)
        
        target_payload = create_alert_payload(severity="warning", service="api")
        target = self._create_incident_with_payload(target_payload)
        
        # Both missing cluster - None == None is True
        assert critical_source_warning_target_rule.equal_labels_match(source, target) is True

    def test_equal_labels_match_no_equal_labels_rule(self, no_equal_labels_rule):
        """Test equal_labels_match with no equal labels configured."""
        source_payload = create_alert_payload(severity="critical", service="api")
        source = self._create_incident_with_payload(source_payload)
        
        target_payload = create_alert_payload(severity="warning", service="different")
        target = self._create_incident_with_payload(target_payload)
        
        # No equal labels means always match
        assert no_equal_labels_rule.equal_labels_match(source, target) is True

    def test_equal_labels_match_empty_common_labels(self, critical_source_warning_target_rule):
        """Test equal_labels_match with empty commonLabels."""
        source = Mock()
        source.payload = {'groupLabels': {'alertname': 'Test'}}  # No commonLabels
        source.uniq_id = "source-1"
        
        target = Mock()
        target.payload = {'groupLabels': {'alertname': 'Test'}}  # No commonLabels
        target.uniq_id = "target-1"
        
        # Both have empty commonLabels, so all labels match (None == None)
        assert critical_source_warning_target_rule.equal_labels_match(source, target) is True

    def test_incident_can_be_both_source_and_target_different_rules(self):
        """Test incident can match as source for one rule and target for another."""
        rule1 = InhibitionRule(
            source_matchers=['severity = "critical"'],
            target_matchers=['severity = "warning"'],
            equal_labels=[]
        )
        rule2 = InhibitionRule(
            source_matchers=['severity = "warning"'],
            target_matchers=['severity = "info"'],
            equal_labels=[]
        )
        
        payload = create_alert_payload(severity="warning")
        incident = self._create_incident_with_payload(payload)
        
        # Target for rule1, source for rule2
        assert rule1.is_target(incident) is True
        assert rule1.is_source(incident) is False
        assert rule2.is_source(incident) is True
        assert rule2.is_target(incident) is False

    def test_negation_matcher(self):
        """Test rule with negation matcher."""
        rule = InhibitionRule(
            source_matchers=['severity != "info"'],
            target_matchers=['severity = "info"'],
            equal_labels=[]
        )
        
        critical_payload = create_alert_payload(severity="critical")
        critical_incident = self._create_incident_with_payload(critical_payload)
        
        info_payload = create_alert_payload(severity="info")
        info_incident = self._create_incident_with_payload(info_payload)
        
        # Critical is source (severity != info)
        assert rule.is_source(critical_incident) is True
        assert rule.is_source(info_incident) is False
        
        # Info is target
        assert rule.is_target(info_incident) is True
        assert rule.is_target(critical_incident) is False

    def test_regex_negation_matcher(self):
        """Test rule with regex negation matcher."""
        rule = InhibitionRule(
            source_matchers=['alertname !~ "Test.*"'],
            target_matchers=['alertname =~ "Test.*"'],
            equal_labels=[]
        )
        
        prod_payload = create_alert_payload(alertname="ProductionAlert")
        prod_incident = self._create_incident_with_payload(prod_payload)
        
        test_payload = create_alert_payload(alertname="TestAlert")
        test_incident = self._create_incident_with_payload(test_payload)
        
        # ProductionAlert is source (doesn't match Test.*)
        assert rule.is_source(prod_incident) is True
        assert rule.is_source(test_incident) is False
        
        # TestAlert is target
        assert rule.is_target(test_incident) is True
        assert rule.is_target(prod_incident) is False
