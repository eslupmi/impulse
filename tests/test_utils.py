"""
Unit tests for app.utils module.
"""
import pytest
from datetime import datetime, timezone

from app.utils import get_attr_by_key_chain, normalize_param, filter_dict_keys


class TestGetAttrByKeyChain:
    """Test cases for get_attr_by_key_chain function."""

    def test_dict_access_single_key(self):
        """Test accessing a single key in a dictionary."""
        data = {"key": "value"}
        result = get_attr_by_key_chain(data, None, "key")
        assert result == "value"

    def test_dict_access_nested_keys(self):
        """Test accessing nested keys in a dictionary."""
        data = {"level1": {"level2": {"level3": "deep_value"}}}
        result = get_attr_by_key_chain(data, None, "level1", "level2", "level3")
        assert result == "deep_value"

    def test_object_attribute_access(self):
        """Test accessing object attributes."""
        class TestObj:
            def __init__(self):
                self.attr = "test_value"
        
        obj = TestObj()
        result = get_attr_by_key_chain(obj, None, "attr")
        assert result == "test_value"

    def test_mixed_dict_and_object_access(self):
        """Test accessing mixed dictionary and object attributes."""
        class TestObj:
            def __init__(self):
                self.nested = {"key": "mixed_value"}
        
        obj = TestObj()
        result = get_attr_by_key_chain(obj, None, "nested", "key")
        assert result == "mixed_value"

    def test_missing_key_returns_default(self):
        """Test that missing keys return the default value."""
        data = {"existing": "value"}
        result = get_attr_by_key_chain(data, "default", "missing")
        assert result == "default"

    def test_missing_nested_key_returns_default(self):
        """Test that missing nested keys return the default value."""
        data = {"level1": {"existing": "value"}}
        result = get_attr_by_key_chain(data, "default", "level1", "missing")
        assert result == "default"

    def test_missing_attribute_returns_default(self):
        """Test that missing attributes return the default value."""
        class TestObj:
            pass
        
        obj = TestObj()
        result = get_attr_by_key_chain(obj, "default", "missing_attr")
        assert result == "default"

    def test_none_object_returns_default(self):
        """Test that None object returns the default value."""
        result = get_attr_by_key_chain(None, "default", "any_key")
        assert result == "default"

    def test_empty_keys_returns_object(self):
        """Test that empty keys return the original object."""
        data = {"key": "value"}
        result = get_attr_by_key_chain(data, "default")
        assert result == data


class TestNormalizeParam:
    """Test cases for normalize_param function."""

    def test_datetime_with_timezone(self):
        """Test normalizing datetime with timezone."""
        dt = datetime(2023, 10, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = normalize_param(dt)
        assert isinstance(result, float)
        assert result == dt.timestamp()

    def test_datetime_without_timezone(self):
        """Test normalizing datetime without timezone (assumes UTC)."""
        dt = datetime(2023, 10, 1, 12, 0, 0)
        result = normalize_param(dt)
        assert isinstance(result, float)
        # Should add UTC timezone and convert to timestamp
        expected = dt.replace(tzinfo=timezone.utc).timestamp()
        assert result == expected

    def test_non_datetime_unchanged(self):
        """Test that non-datetime objects are returned unchanged."""
        test_cases = [
            "string",
            123,
            123.45,
            True,
            False,
            None,
            [],
            {},
            {"key": "value"}
        ]
        
        for test_case in test_cases:
            result = normalize_param(test_case)
            assert result == test_case
            assert type(result) == type(test_case)


class TestFilterDictKeys:
    """Test cases for filter_dict_keys function."""

    def test_filter_existing_keys(self):
        """Test filtering out existing keys."""
        source = {"a": 1, "b": 2, "c": 3, "d": 4}
        keys_to_exclude = {"b": "any_value", "d": "any_value"}
        result = filter_dict_keys(source, keys_to_exclude)
        expected = {"a": 1, "c": 3}
        assert result == expected

    def test_filter_non_existing_keys(self):
        """Test filtering with keys that don't exist in source."""
        source = {"a": 1, "b": 2}
        keys_to_exclude = {"x": "value", "y": "value"}
        result = filter_dict_keys(source, keys_to_exclude)
        assert result == source

    def test_filter_empty_exclusion_dict(self):
        """Test filtering with empty exclusion dictionary."""
        source = {"a": 1, "b": 2, "c": 3}
        keys_to_exclude = {}
        result = filter_dict_keys(source, keys_to_exclude)
        assert result == source

    def test_filter_empty_source_dict(self):
        """Test filtering with empty source dictionary."""
        source = {}
        keys_to_exclude = {"a": "value"}
        result = filter_dict_keys(source, keys_to_exclude)
        assert result == {}

    def test_filter_all_keys(self):
        """Test filtering out all keys."""
        source = {"a": 1, "b": 2}
        keys_to_exclude = {"a": "value", "b": "value"}
        result = filter_dict_keys(source, keys_to_exclude)
        assert result == {}

    def test_original_dict_unchanged(self):
        """Test that the original dictionary is not modified."""
        source = {"a": 1, "b": 2, "c": 3}
        keys_to_exclude = {"b": "value"}
        original_source = source.copy()
        
        result = filter_dict_keys(source, keys_to_exclude)
        
        # Original should be unchanged
        assert source == original_source
        # Result should be different
        assert result != source
        assert result == {"a": 1, "c": 3}
