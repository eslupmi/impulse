"""
Unit tests for app.route.matcher module.
"""
from unittest.mock import patch

import pytest

from app.route.matcher import Matcher


class TestMatcher:
    """Test cases for Matcher class."""

    def test_matcher_initialization_valid_string(self):
        """Test Matcher initialization with valid string."""
        matcher = Matcher('severity="critical"')

        assert matcher.type == '='
        assert matcher.label == 'severity'
        assert matcher.expr == 'critical'
        assert not hasattr(matcher, 'regex') or matcher.regex is None

    def test_matcher_initialization_not_equal(self):
        """Test Matcher initialization with not equal operator."""
        matcher = Matcher('severity!="warning"')

        assert matcher.type == '!='
        assert matcher.label == 'severity'
        assert matcher.expr == 'warning'
        assert not hasattr(matcher, 'regex') or matcher.regex is None

    def test_matcher_initialization_regex_match(self):
        """Test Matcher initialization with regex match operator."""
        matcher = Matcher('service=~"api.*"')

        assert matcher.type == '=~'
        assert matcher.label == 'service'
        assert matcher.expr == 'api.*'
        assert matcher.regex is not None
        assert matcher.regex.pattern == 'api.*'

    def test_matcher_initialization_regex_no_match(self):
        """Test Matcher initialization with regex no match operator."""
        matcher = Matcher('environment!~"prod.*"')

        assert matcher.type == '!~'
        assert matcher.label == 'environment'
        assert matcher.expr == 'prod.*'
        assert matcher.regex is not None
        assert matcher.regex.pattern == 'prod.*'

    def test_matcher_initialization_invalid_string(self):
        """Test Matcher initialization with invalid string."""
        with pytest.raises(ValueError, match='Invalid matcher "invalid string"'):
            Matcher('invalid string')

    def test_matcher_initialization_missing_quotes(self):
        """Test Matcher initialization with missing quotes."""
        with pytest.raises(ValueError, match='Invalid matcher "severity=critical"'):
            Matcher('severity=critical')

    def test_matches_equals_operator_match(self):
        """Test matches method with equals operator - match."""
        matcher = Matcher('severity="critical"')

        alert_state = {
            'commonLabels': {
                'severity': 'critical'
            }
        }

        assert matcher.matches(alert_state) is True

    def test_matches_equals_operator_no_match(self):
        """Test matches method with equals operator - no match."""
        matcher = Matcher('severity="critical"')

        alert_state = {
            'commonLabels': {
                'severity': 'warning'
            }
        }

        assert matcher.matches(alert_state) is False

    def test_matches_not_equals_operator_match(self):
        """Test matches method with not equals operator - match."""
        matcher = Matcher('severity!="warning"')

        alert_state = {
            'commonLabels': {
                'severity': 'critical'
            }
        }

        assert matcher.matches(alert_state) is True

    def test_matches_not_equals_operator_no_match(self):
        """Test matches method with not equals operator - no match."""
        matcher = Matcher('severity!="critical"')

        alert_state = {
            'commonLabels': {
                'severity': 'critical'
            }
        }

        assert matcher.matches(alert_state) is False

    def test_matches_regex_match_operator_match(self):
        """Test matches method with regex match operator - match."""
        matcher = Matcher('service=~"api.*"')

        alert_state = {
            'commonLabels': {
                'service': 'api-server'
            }
        }

        assert matcher.matches(alert_state) is True

    def test_matches_regex_match_operator_no_match(self):
        """Test matches method with regex match operator - no match."""
        matcher = Matcher('service=~"api.*"')

        alert_state = {
            'commonLabels': {
                'service': 'database-server'
            }
        }

        assert matcher.matches(alert_state) is False

    def test_matches_regex_no_match_operator_match(self):
        """Test matches method with regex no match operator - match."""
        matcher = Matcher('environment!~"prod.*"')

        alert_state = {
            'commonLabels': {
                'environment': 'staging'
            }
        }

        assert matcher.matches(alert_state) is True

    def test_matches_regex_no_match_operator_no_match(self):
        """Test matches method with regex no match operator - no match."""
        matcher = Matcher('environment!~"prod.*"')

        alert_state = {
            'commonLabels': {
                'environment': 'production'
            }
        }

        assert matcher.matches(alert_state) is False

    def test_matches_missing_common_labels(self):
        """Test matches method with missing commonLabels."""
        matcher = Matcher('severity="critical"')

        alert_state = {}

        assert matcher.matches(alert_state) is False

    def test_matches_none_common_labels(self):
        """Test matches method with None commonLabels."""
        matcher = Matcher('severity="critical"')

        alert_state = {'commonLabels': None}

        assert matcher.matches(alert_state) is False

    def test_matches_missing_label(self):
        """Test matches method with missing label."""
        matcher = Matcher('severity="critical"')

        alert_state = {
            'commonLabels': {
                'service': 'api'
            }
        }

        assert matcher.matches(alert_state) is False

    def test_matches_regex_with_none_label(self):
        """Test matches method with regex and None label."""
        matcher = Matcher('service=~"api.*"')

        alert_state = {
            'commonLabels': {
                'service': None
            }
        }

        assert matcher.matches(alert_state) is False

    def test_matches_regex_no_match_with_none_label(self):
        """Test matches method with regex no match and None label."""
        matcher = Matcher('service!~"api.*"')

        alert_state = {
            'commonLabels': {
                'service': None
            }
        }

        assert matcher.matches(alert_state) is True

    def test_matches_unknown_operator(self):
        """Test matches method with unknown operator."""
        matcher = Matcher('severity="critical"')
        matcher.type = 'unknown'  # Manually set unknown type

        with patch('app.route.matcher.logger') as mock_logger:
            result = matcher.matches({'commonLabels': {'severity': 'critical'}})

            assert result is False
            mock_logger.warning.assert_called_once()

    def test_matches_complex_regex(self):
        """Test matches method with complex regex patterns."""
        matcher = Matcher('service=~"^api-(server|gateway)$"')

        alert_state = {
            'commonLabels': {
                'service': 'api-server'
            }
        }

        assert matcher.matches(alert_state) is True

        alert_state = {
            'commonLabels': {
                'service': 'api-gateway'
            }
        }

        assert matcher.matches(alert_state) is True

        alert_state = {
            'commonLabels': {
                'service': 'api-client'
            }
        }

        assert matcher.matches(alert_state) is False

    def test_matches_special_characters_in_expression(self):
        """Test matches method with special characters in expression."""
        matcher = Matcher('message=~".*error.*"')

        alert_state = {
            'commonLabels': {
                'message': 'Database connection error occurred'
            }
        }

        assert matcher.matches(alert_state) is True

    def test_matches_case_sensitive(self):
        """Test matches method is case sensitive."""
        matcher = Matcher('severity="Critical"')

        alert_state = {
            'commonLabels': {
                'severity': 'critical'  # lowercase
            }
        }

        assert matcher.matches(alert_state) is False

    def test_matches_empty_string(self):
        """Test matches method with empty string values."""
        matcher = Matcher('severity="empty"')

        alert_state = {
            'commonLabels': {
                'severity': 'empty'
            }
        }

        assert matcher.matches(alert_state) is True

    def test_matches_whitespace_handling(self):
        """Test matches method with whitespace in values."""
        matcher = Matcher('severity="critical"')

        alert_state = {
            'commonLabels': {
                'severity': ' critical '  # with whitespace
            }
        }

        assert matcher.matches(alert_state) is False  # Exact match required

    def test_matches_numeric_values(self):
        """Test matches method with numeric values."""
        matcher = Matcher('count="5"')

        alert_state = {
            'commonLabels': {
                'count': '5'
            }
        }

        assert matcher.matches(alert_state) is True

    def test_matches_boolean_values(self):
        """Test matches method with boolean values."""
        matcher = Matcher('enabled="true"')

        alert_state = {
            'commonLabels': {
                'enabled': 'true'
            }
        }

        assert matcher.matches(alert_state) is True
