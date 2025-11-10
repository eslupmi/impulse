"""
Unit tests for Incident.gen_uuid and gen_uniq_id methods.
"""
import uuid
from datetime import datetime, timezone

import pytest

from app.incident.incident import Incident


class TestGenUuid:
    """Test cases for Incident.gen_uuid method."""

    def test_gen_uuid_basic_functionality(self):
        """Test basic UUID generation with different input types."""
        # Test with dictionary
        data = {'alertname': 'TestAlert', 'severity': 'critical'}
        result = Incident.gen_uuid(data)
        assert isinstance(result, str)
        # Should be a valid UUID string
        uuid.UUID(result)

        # Test with None
        result = Incident.gen_uuid(None)
        assert isinstance(result, str)
        uuid.UUID(result)

        # Test with empty dict
        result = Incident.gen_uuid({})
        assert isinstance(result, str)
        uuid.UUID(result)

    def test_gen_uuid_consistency(self):
        """Test that gen_uuid returns consistent results for same input."""
        data = {'alertname': 'TestAlert', 'severity': 'critical'}

        result1 = Incident.gen_uuid(data)
        result2 = Incident.gen_uuid(data)

        assert result1 == result2

    def test_gen_uuid_different_inputs(self):
        """Test that gen_uuid returns different results for different inputs."""
        data1 = {'alertname': 'TestAlert1', 'severity': 'critical'}
        data2 = {'alertname': 'TestAlert2', 'severity': 'critical'}

        result1 = Incident.gen_uuid(data1)
        result2 = Incident.gen_uuid(data2)

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

        result = Incident.gen_uuid(data)
        assert isinstance(result, str)
        uuid.UUID(result)


class TestGenUniqId:
    """Test cases for Incident.gen_uniq_id method."""

    def test_gen_uniq_id_basic_functionality(self):
        """Test basic uniq_id generation with different input types."""
        # Test with dictionary and datetime
        data = {'alertname': 'TestAlert', 'severity': 'critical'}
        dt = datetime.now(timezone.utc)
        result = Incident.gen_uniq_id(data, dt)
        assert isinstance(result, str)
        # Should be a valid UUID string
        uuid.UUID(result)

        # Test with None
        result = Incident.gen_uniq_id(None, dt)
        assert isinstance(result, str)
        uuid.UUID(result)

        # Test with empty dict
        result = Incident.gen_uniq_id({}, dt)
        assert isinstance(result, str)
        uuid.UUID(result)

    def test_gen_uniq_id_consistency(self):
        """Test that gen_uniq_id returns consistent results for same input."""
        data = {'alertname': 'TestAlert', 'severity': 'critical'}
        dt = datetime.now(timezone.utc)

        result1 = Incident.gen_uniq_id(data, dt)
        result2 = Incident.gen_uniq_id(data, dt)

        assert result1 == result2

    def test_gen_uniq_id_different_inputs(self):
        """Test that gen_uniq_id returns different results for different inputs."""
        data1 = {'alertname': 'TestAlert1', 'severity': 'critical'}
        data2 = {'alertname': 'TestAlert2', 'severity': 'critical'}
        dt = datetime.now(timezone.utc)

        result1 = Incident.gen_uniq_id(data1, dt)
        result2 = Incident.gen_uniq_id(data2, dt)

        assert result1 != result2

    def test_gen_uniq_id_different_datetime(self):
        """Test that gen_uniq_id returns different results for different datetime."""
        data = {'alertname': 'TestAlert', 'severity': 'critical'}
        dt1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2025, 1, 1, 13, 0, 0, tzinfo=timezone.utc)

        result1 = Incident.gen_uniq_id(data, dt1)
        result2 = Incident.gen_uniq_id(data, dt2)

        assert result1 != result2
