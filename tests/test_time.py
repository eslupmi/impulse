"""
Unit tests for app.time module.
"""
from datetime import timedelta

import pytest

from app.time import unix_sleep_to_timedelta


class TestUnixSleepToTimedelta:
    """Test cases for unix_sleep_to_timedelta function."""

    def test_seconds_conversion(self):
        """Test conversion of seconds."""
        result = unix_sleep_to_timedelta("30s")
        expected = timedelta(seconds=30)
        assert result == expected

    def test_minutes_conversion(self):
        """Test conversion of minutes."""
        result = unix_sleep_to_timedelta("45m")
        expected = timedelta(minutes=45)
        assert result == expected

    def test_hours_conversion(self):
        """Test conversion of hours."""
        result = unix_sleep_to_timedelta("2h")
        expected = timedelta(hours=2)
        assert result == expected

    def test_days_conversion(self):
        """Test conversion of days."""
        result = unix_sleep_to_timedelta("7d")
        expected = timedelta(days=7)
        assert result == expected

    def test_single_digit_values(self):
        """Test conversion with single digit values."""
        test_cases = [
            ("1s", timedelta(seconds=1)),
            ("1m", timedelta(minutes=1)),
            ("1h", timedelta(hours=1)),
            ("1d", timedelta(days=1))
        ]

        for input_val, expected in test_cases:
            result = unix_sleep_to_timedelta(input_val)
            assert result == expected

    def test_multi_digit_values(self):
        """Test conversion with multi-digit values."""
        test_cases = [
            ("120s", timedelta(seconds=120)),
            ("90m", timedelta(minutes=90)),
            ("24h", timedelta(hours=24)),
            ("90d", timedelta(days=90))
        ]

        for input_val, expected in test_cases:
            result = unix_sleep_to_timedelta(input_val)
            assert result == expected

    def test_zero_values(self):
        """Test conversion with zero values."""
        test_cases = [
            ("0s", timedelta(seconds=0)),
            ("0m", timedelta(minutes=0)),
            ("0h", timedelta(hours=0)),
            ("0d", timedelta(days=0))
        ]

        for input_val, expected in test_cases:
            result = unix_sleep_to_timedelta(input_val)
            assert result == expected

    def test_large_values(self):
        """Test conversion with large values."""
        result = unix_sleep_to_timedelta("9999s")
        expected = timedelta(seconds=9999)
        assert result == expected

    def test_invalid_unit_raises_keyerror(self):
        """Test that invalid time units raise KeyError."""
        with pytest.raises(KeyError):
            unix_sleep_to_timedelta("30x")  # 'x' is not a valid unit

    def test_invalid_format_raises_valueerror(self):
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError):
            unix_sleep_to_timedelta("abc")  # No numeric part

    def test_empty_string_raises_error(self):
        """Test that empty string raises an error."""
        with pytest.raises((ValueError, IndexError)):
            unix_sleep_to_timedelta("")

    def test_only_unit_raises_error(self):
        """Test that string with only unit raises an error."""
        with pytest.raises(ValueError):
            unix_sleep_to_timedelta("s")

    def test_only_number_raises_error(self):
        """Test that string with only number raises an error."""
        with pytest.raises(KeyError):
            unix_sleep_to_timedelta("30")

    def test_negative_values(self):
        """Test conversion with negative values (if supported)."""
        # Note: The function might not handle negative values well,
        # but we test the behavior
        try:
            result = unix_sleep_to_timedelta("-30s")
            expected = timedelta(seconds=-30)
            assert result == expected
        except ValueError:
            # If negative values are not supported, that's also valid behavior
            pass

    def test_float_values_raises_error(self):
        """Test that float values raise a ValueError."""
        # The function doesn't handle float values
        with pytest.raises(ValueError):
            unix_sleep_to_timedelta("30.7s")
