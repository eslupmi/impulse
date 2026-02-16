"""
Unit tests for time utility functions.

This module tests the time-related utility functions including freeze time calculations
and formatting functions.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from app.time import (
    unix_sleep_to_timedelta,
    add_months,
    calculate_freeze_time,
    format_freeze_expiration
)


class TestUnixSleepToTimedelta:
    """Test cases for unix_sleep_to_timedelta function."""

    def test_seconds_conversion(self):
        """Test converting seconds to timedelta."""
        result = unix_sleep_to_timedelta('30s')
        assert result == timedelta(seconds=30)

    def test_minutes_conversion(self):
        """Test converting minutes to timedelta."""
        result = unix_sleep_to_timedelta('15m')
        assert result == timedelta(minutes=15)

    def test_hours_conversion(self):
        """Test converting hours to timedelta."""
        result = unix_sleep_to_timedelta('2h')
        assert result == timedelta(hours=2)

    def test_days_conversion(self):
        """Test converting days to timedelta."""
        result = unix_sleep_to_timedelta('7d')
        assert result == timedelta(days=7)

    def test_large_values(self):
        """Test converting large values."""
        result = unix_sleep_to_timedelta('1440m')  # 24 hours
        assert result == timedelta(minutes=1440)


class TestAddMonths:
    """Test cases for _add_months function."""

    def test_add_one_month(self):
        """Test adding one month."""
        source = datetime(2023, 1, 15, 10, 30, 0)
        result = add_months(source, 1)
        assert result.year == 2023
        assert result.month == 2
        assert result.day == 15

    def test_add_multiple_months(self):
        """Test adding multiple months."""
        source = datetime(2023, 1, 15, 10, 30, 0)
        result = add_months(source, 6)
        assert result.year == 2023
        assert result.month == 7
        assert result.day == 15

    def test_add_months_crossing_year(self):
        """Test adding months that cross year boundary."""
        source = datetime(2023, 11, 15, 10, 30, 0)
        result = add_months(source, 3)
        assert result.year == 2024
        assert result.month == 2
        assert result.day == 15

    def test_add_months_end_of_month(self):
        """Test adding months with end-of-month date."""
        source = datetime(2023, 1, 31, 10, 30, 0)
        result = add_months(source, 1)
        # February has only 28/29 days, so day should be adjusted
        assert result.year == 2023
        assert result.month == 2
        assert result.day == 28

    def test_add_months_leap_year(self):
        """Test adding months with leap year."""
        source = datetime(2024, 1, 31, 10, 30, 0)
        result = add_months(source, 1)
        # February 2024 is a leap year, so has 29 days
        assert result.year == 2024
        assert result.month == 2
        assert result.day == 29

    def test_add_twelve_months(self):
        """Test adding 12 months (one year)."""
        source = datetime(2023, 1, 15, 10, 30, 0)
        result = add_months(source, 12)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15


class TestCalculateFreezeTime:
    """Test cases for calculate_freeze_time function."""

    @pytest.fixture
    def mock_config(self):
        """Create mock general config."""
        config = Mock()
        config.workday_start = "09:00"
        config.week_start = "Mon"
        return config

    def test_calculate_tomorrow_utc(self, mock_config):
        """Test calculating freeze time for tomorrow in UTC."""
        result = calculate_freeze_time('tomorrow', mock_config, 'UTC')
        
        # Should be tomorrow at 9:00 UTC
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc
        assert result.hour == 9
        assert result.minute == 0

    def test_calculate_tomorrow_with_timezone(self, mock_config):
        """Test calculating freeze time for tomorrow with timezone."""
        result = calculate_freeze_time('tomorrow', mock_config, 'America/New_York')
        
        # Should be tomorrow at 9:00 AM NY time, converted to UTC
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc

    def test_calculate_next_monday(self, mock_config):
        """Test calculating freeze time for next Monday."""
        result = calculate_freeze_time('next_monday', mock_config, 'UTC')
        
        # Should be next Monday at 9:00 UTC
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc
        assert result.hour == 9
        assert result.minute == 0
        assert result.weekday() == 0  # Monday

    def test_calculate_next_monday_different_week_start(self, mock_config):
        """Test calculating next Monday with different week start."""
        mock_config.week_start = "Wed"
        result = calculate_freeze_time('next_monday', mock_config, 'UTC')
        
        # Should be next Wednesday at 9:00 UTC
        assert isinstance(result, datetime)
        assert result.weekday() == 2  # Wednesday

    def test_calculate_month(self, mock_config):
        """Test calculating freeze time for one month."""
        result = calculate_freeze_time('month', mock_config, 'UTC')
        
        # Should be approximately one month from now
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc
        assert result.hour == 9
        assert result.minute == 0

    def test_calculate_six_months(self, mock_config):
        """Test calculating freeze time for six months."""
        result = calculate_freeze_time('6months', mock_config, 'UTC')
        
        # Should be approximately six months from now
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc
        assert result.hour == 9
        assert result.minute == 0

    def test_calculate_with_custom_workday_start(self, mock_config):
        """Test calculating freeze time with custom workday start."""
        mock_config.workday_start = "08:30"
        result = calculate_freeze_time('tomorrow', mock_config, 'UTC')
        
        assert result.hour == 8
        assert result.minute == 30

    def test_calculate_invalid_option(self, mock_config):
        """Test calculating freeze time with invalid option."""
        with pytest.raises(ValueError, match="Unknown freeze option"):
            calculate_freeze_time('invalid_option', mock_config, 'UTC')

    def test_calculate_with_numeric_week_start(self, mock_config):
        """Test calculating with numeric week start."""
        mock_config.week_start = "1"  # Monday
        result = calculate_freeze_time('next_monday', mock_config, 'UTC')
        
        assert result.weekday() == 0  # Monday

    def test_calculate_with_sunday_week_start(self, mock_config):
        """Test calculating with Sunday as week start."""
        mock_config.week_start = "Sun"
        result = calculate_freeze_time('next_monday', mock_config, 'UTC')
        
        assert result.weekday() == 6  # Sunday


class TestFormatFreezeExpiration:
    """Test cases for format_freeze_expiration function."""

    def test_format_within_week(self):
        """Test formatting freeze expiration within the next 7 days."""
        # Create a freeze time 2 days from now
        frozen_until = datetime.now(timezone.utc) + timedelta(days=2)
        result = format_freeze_expiration(frozen_until, 'UTC')
        
        # Should return day name and time like "Wed 12:00"
        assert len(result.split()) == 2
        # First part should be day abbreviation (3 letters)
        assert len(result.split()[0]) == 3

    def test_format_beyond_week(self):
        """Test formatting freeze expiration beyond 7 days."""
        # Create a freeze time 10 days from now
        frozen_until = datetime.now(timezone.utc) + timedelta(days=10)
        result = format_freeze_expiration(frozen_until, 'UTC')
        
        # Should return month and day like "Jan 15"
        assert len(result.split()) == 2
        # First part should be month abbreviation (3 letters)
        assert len(result.split()[0]) == 3

    def test_format_with_timezone(self):
        """Test formatting with specific timezone."""
        frozen_until = datetime.now(timezone.utc) + timedelta(days=2, hours=5)
        result = format_freeze_expiration(frozen_until, 'America/New_York')
        
        # Should format in NY timezone
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_exactly_seven_days(self):
        """Test formatting at exactly 7 days boundary."""
        frozen_until = datetime.now(timezone.utc) + timedelta(days=7, hours=1)
        result = format_freeze_expiration(frozen_until, 'UTC')
        
        # Should use date format (beyond 7 days)
        assert len(result.split()) == 2

    def test_format_one_day_ahead(self):
        """Test formatting one day ahead."""
        frozen_until = datetime.now(timezone.utc) + timedelta(days=1)
        result = format_freeze_expiration(frozen_until, 'UTC')
        
        # Should return day name and time
        parts = result.split()
        assert len(parts) == 2
        # Time should be in HH:MM format
        assert ':' in parts[1]

    def test_format_with_specific_time(self):
        """Test formatting with specific time."""
        tz = ZoneInfo('UTC')
        now = datetime.now(tz)
        frozen_until = now.replace(hour=14, minute=30) + timedelta(days=3)
        result = format_freeze_expiration(frozen_until, 'UTC')
        
        # Should include the specific time
        assert '14:30' in result or '14' in result
