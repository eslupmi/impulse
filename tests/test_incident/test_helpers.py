"""
Unit tests for app.incident.helpers module.
"""
import uuid

import pytest

from app.incident.helpers import gen_uuid


class TestGenUuid:
    """Test cases for gen_uuid function."""

    def test_gen_uuid_basic_functionality(self):
        """Test basic UUID generation with different input types."""
        # Test with dictionary
        data = {'alertname': 'TestAlert', 'severity': 'critical'}
        result = gen_uuid(data)
        assert isinstance(result, uuid.UUID)

        # Test with None
        result = gen_uuid(None)
        assert isinstance(result, uuid.UUID)

        # Test with empty dict
        result = gen_uuid({})
        assert isinstance(result, uuid.UUID)

    def test_gen_uuid_consistency(self):
        """Test that gen_uuid returns consistent results for same input."""
        data = {'alertname': 'TestAlert', 'severity': 'critical'}

        result1 = gen_uuid(data)
        result2 = gen_uuid(data)

        assert result1 == result2

    def test_gen_uuid_different_inputs(self):
        """Test that gen_uuid returns different results for different inputs."""
        data1 = {'alertname': 'TestAlert1', 'severity': 'critical'}
        data2 = {'alertname': 'TestAlert2', 'severity': 'critical'}

        result1 = gen_uuid(data1)
        result2 = gen_uuid(data2)

        assert result1 != result2

    def test_gen_uuid_with_complex_data(self):
        """Test gen_uuid with complex nested data."""
        data = {
            'alertname': 'TestAlert',
            'labels': {'severity': 'critical', 'service': 'api'},
            'annotations': {'summary': 'Test alert'},
            'count': 5,
            'enabled': True
        }

        result = gen_uuid(data)
        assert isinstance(result, uuid.UUID)
