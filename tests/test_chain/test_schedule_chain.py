"""
Unit tests for app.im.chain.schedule_chain module.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.config.validation import ScheduleEntry, ScheduleMatcherExpression, SimpleChainStep
from app.im.chain.schedule_chain import ScheduleChain


class TestScheduleChainInit:
    """Test cases for ScheduleChain initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        chain = ScheduleChain(name="test_chain")

        assert chain.name == "test_chain"
        assert chain.timezone == "UTC"
        assert chain.schedule == []
        assert isinstance(chain.tz, ZoneInfo)

    def test_init_with_custom_timezone(self):
        """Test initialization with custom timezone."""
        chain = ScheduleChain(name="test_chain", timezone_="America/New_York")

        assert chain.name == "test_chain"
        assert chain.timezone == "America/New_York"
        assert str(chain.tz) == "America/New_York"

    def test_init_with_schedule(self):
        """Test initialization with schedule entries."""
        schedule = [
            ScheduleEntry(
                matcher=ScheduleMatcherExpression(
                    start_day_expr="dow",
                    start_day_values=[1, 2, 3],
                    start_time="09:00",
                    duration="8h"
                ),
                steps=[SimpleChainStep(user="test_user")]
            )
        ]

        chain = ScheduleChain(name="test_chain", schedule=schedule)

        assert len(chain.schedule) == 1
        assert chain.schedule[0].steps[0].user == "test_user"

    def test_repr(self):
        """Test string representation."""
        chain = ScheduleChain(name="my_chain")
        assert repr(chain) == "my_chain"


class TestScheduleChainSteps:
    """Test cases for getting steps from schedule."""

    def test_get_steps_with_empty_schedule(self):
        """Test getting steps when schedule is empty."""
        chain = ScheduleChain(name="test_chain")
        steps = chain.steps

        assert steps == []

    def test_get_steps_with_matcher_match(self):
        """Test getting steps when matcher condition matches."""
        # Create a schedule entry that matches current day
        now = datetime.now(ZoneInfo("UTC"))
        current_dow = (now.weekday() + 1) % 7  # Convert to Sunday=0 format

        schedule = [
            ScheduleEntry(
                matcher=ScheduleMatcherExpression(
                    start_day_expr="dow",
                    start_day_values=[current_dow],
                    start_time="00:00",
                    duration="24h"
                ),
                steps=[SimpleChainStep(user="test_user")]
            )
        ]

        chain = ScheduleChain(name="test_chain", schedule=schedule)
        steps = chain.steps

        assert len(steps) == 1
        assert steps[0].user == "test_user"

    def test_get_steps_with_no_matcher(self):
        """Test getting steps when entry has no matcher (default steps)."""
        schedule = [
            ScheduleEntry(
                matcher=None,
                steps=[SimpleChainStep(user="default_user")]
            )
        ]

        chain = ScheduleChain(name="test_chain", schedule=schedule)
        steps = chain.steps

        assert len(steps) == 1
        assert steps[0].user == "default_user"


class TestScheduleChainDayConditions:
    """Test cases for day condition checking."""

    def test_match_dow_condition_with_number(self):
        """Test day of week matching with numeric values."""
        # Test Monday (1 in Sunday=0 format)
        assert ScheduleChain._match_dow_condition(1, [1, 2, 3]) is True
        assert ScheduleChain._match_dow_condition(1, [4, 5, 6]) is False

    def test_match_dow_condition_with_string(self):
        """Test day of week matching with string values."""
        assert ScheduleChain._match_dow_condition(1, ["Mon", "Tue"]) is True
        assert ScheduleChain._match_dow_condition(1, ["Wed", "Thu"]) is False

    def test_match_dom_condition(self):
        """Test day of month matching."""
        assert ScheduleChain._match_dom_condition(15, [15, 20, 25]) is True
        assert ScheduleChain._match_dom_condition(15, [10, 20, 25]) is False
        assert ScheduleChain._match_dom_condition(1, [1]) is True
        assert ScheduleChain._match_dom_condition(31, [31]) is True

    def test_match_date_condition(self):
        """Test specific date matching."""
        assert ScheduleChain._match_date_condition("2024-01-15", ["2024-01-15", "2024-01-20"]) is True
        assert ScheduleChain._match_date_condition("2024-01-15", ["2024-01-20", "2024-01-25"]) is False

    def test_check_day_condition_dow(self):
        """Test check day condition with day of week."""
        chain = ScheduleChain(name="test_chain")
        test_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=ZoneInfo("UTC"))  # Monday

        # Monday is 1 in Sunday=0 format
        result = chain._match_day_condition("dow", [1], test_time)
        assert result is True

        result = chain._match_day_condition("dow", [0], test_time)  # Sunday
        assert result is False

    def test_check_day_condition_dom(self):
        """Test check day condition with day of month."""
        chain = ScheduleChain(name="test_chain")
        test_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=ZoneInfo("UTC"))

        result = chain._match_day_condition("dom", [15], test_time)
        assert result is True

        result = chain._match_day_condition("dom", [1, 10, 20], test_time)
        assert result is False

    def test_check_day_condition_date(self):
        """Test check day condition with specific date."""
        chain = ScheduleChain(name="test_chain")
        test_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=ZoneInfo("UTC"))

        result = chain._match_day_condition("date", ["2024-01-15"], test_time)
        assert result is True

        result = chain._match_day_condition("date", ["2024-01-20"], test_time)
        assert result is False

    def test_check_day_condition_with_modulo(self):
        """Test check day condition with modulo operator."""
        chain = ScheduleChain(name="test_chain")
        test_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=ZoneInfo("UTC"))  # 15th day

        result = chain._match_day_condition("dom % 2", [1], test_time)
        assert result is True

        result = chain._match_day_condition("dom % 2", [0], test_time)
        assert result is False


class TestScheduleChainShiftTime:
    """Test cases for shift time calculations."""

    def test_get_shift_time(self):
        """Test getting shift start and end time."""
        test_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=ZoneInfo("UTC"))

        shift_start, shift_end = ScheduleChain._get_shift_time("09:00", "8h", test_time)

        assert shift_start.hour == 9
        assert shift_start.minute == 0
        assert shift_end == shift_start + timedelta(hours=8)

    def test_get_shift_time_different_durations(self):
        """Test getting shift time with different duration formats."""
        test_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=ZoneInfo("UTC"))

        test_cases = [
            ("09:00", "30m", timedelta(minutes=30)),
            ("14:30", "2h", timedelta(hours=2)),
            ("08:00", "1d", timedelta(days=1)),
            ("00:00", "45s", timedelta(seconds=45)),
        ]

        for start_time, duration, expected_delta in test_cases:
            shift_start, shift_end = ScheduleChain._get_shift_time(start_time, duration, test_time)
            assert shift_end - shift_start == expected_delta

    def test_within_shift_time_inside_window(self):
        """Test within shift time when current time is inside window."""
        chain = ScheduleChain(name="test_chain", timezone_="UTC")

        # Get current time in UTC
        now = datetime.now(ZoneInfo("UTC"))
        current_hour = now.hour

        # Create a shift that includes current time
        start_time = f"{current_hour:02d}:00"
        duration = "2h"

        result = chain._within_shift_time(start_time, duration, now)
        assert result is True

    def test_within_shift_time_outside_window(self):
        """Test within shift time when current time is outside window."""
        chain = ScheduleChain(name="test_chain", timezone_="UTC")

        # Get current time in UTC
        now = datetime.now(ZoneInfo("UTC"))

        # Create a shift that's 12 hours ago (should be outside window)
        past_hour = (now.hour - 12) % 24
        start_time = f"{past_hour:02d}:00"
        duration = "1h"

        result = chain._within_shift_time(start_time, duration, now)
        assert result is False

    def test_get_duration(self):
        """Test getting duration from string."""
        result = ScheduleChain._get_duration("8h")
        assert result == "8h"

        result = ScheduleChain._get_duration(None)
        assert result is None


class TestScheduleChainMatchConditions:
    """Test cases for matching conditions."""

    def test_match_conditions_day_only(self):
        """Test matching conditions with only day condition."""
        chain = ScheduleChain(name="test_chain", timezone_="UTC")
        test_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=ZoneInfo("UTC"))  # Monday

        matcher = ScheduleMatcherExpression(
            start_day_expr="dow",
            start_day_values=[1],  # Monday
            start_time=None,
            duration=None
        )

        result = chain._match_conditions(matcher, test_time)
        assert result is True

    def test_match_conditions_day_and_time_match(self):
        """Test matching conditions with both day and time matching."""
        chain = ScheduleChain(name="test_chain", timezone_="UTC")

        # Use actual current time for this test since _within_shift_time uses datetime.now()
        now = datetime.now(ZoneInfo("UTC"))
        current_dow = (now.weekday() + 1) % 7

        # Create a shift that includes current time
        current_hour = now.hour
        start_time = f"{current_hour:02d}:00"

        matcher = ScheduleMatcherExpression(
            start_day_expr="dow",
            start_day_values=[current_dow],
            start_time=start_time,
            duration="2h"
        )

        result = chain._match_conditions(matcher, now)
        assert result is True

    def test_match_conditions_day_match_time_no_match(self):
        """Test matching conditions with day matching but time not matching."""
        chain = ScheduleChain(name="test_chain", timezone_="UTC")
        test_time = datetime(2024, 1, 15, 20, 0, 0, tzinfo=ZoneInfo("UTC"))  # Monday 20:00

        matcher = ScheduleMatcherExpression(
            start_day_expr="dow",
            start_day_values=[1],  # Monday
            start_time="09:00",
            duration="8h"  # 09:00 - 17:00
        )

        result = chain._match_conditions(matcher, test_time)
        assert result is False

    def test_match_conditions_specific_date(self):
        """Test matching conditions with specific date."""
        chain = ScheduleChain(name="test_chain", timezone_="UTC")

        # Use actual current time since _within_shift_time uses datetime.now()
        now = datetime.now(ZoneInfo("UTC"))
        current_date = now.strftime('%Y-%m-%d')
        current_hour = now.hour
        start_time = f"{current_hour:02d}:00"

        matcher = ScheduleMatcherExpression(
            start_day_expr="date",
            start_day_values=[current_date],
            start_time=start_time,
            duration="2h"
        )

        result = chain._match_conditions(matcher, now)
        assert result is True

    def test_match_conditions_no_match(self):
        """Test matching conditions when nothing matches."""
        chain = ScheduleChain(name="test_chain", timezone_="UTC")
        test_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=ZoneInfo("UTC"))  # Monday

        matcher = ScheduleMatcherExpression(
            start_day_expr="dow",
            start_day_values=[0],  # Sunday
            start_time="09:00",
            duration="8h"
        )

        result = chain._match_conditions(matcher, test_time)
        assert result is False


class TestScheduleChainHelpers:
    """Test cases for helper functions."""

    def test_calculate_days_difference_same_day(self):
        """Test calculating days difference for same day."""
        start = datetime(2024, 1, 15, 9, 0, 0)
        end = datetime(2024, 1, 15, 17, 0, 0)

        result = ScheduleChain.calculate_days_difference(start, end)
        assert result == 0

    def test_calculate_days_difference_next_day(self):
        """Test calculating days difference for next day."""
        start = datetime(2024, 1, 15, 9, 0, 0)
        end = datetime(2024, 1, 16, 9, 0, 0)

        result = ScheduleChain.calculate_days_difference(start, end)
        assert result == 1

    def test_calculate_days_difference_multiple_days(self):
        """Test calculating days difference for multiple days."""
        start = datetime(2024, 1, 15, 9, 0, 0)
        end = datetime(2024, 1, 20, 9, 0, 0)

        result = ScheduleChain.calculate_days_difference(start, end)
        assert result == 5

    def test_calculate_days_difference_reversed_dates(self):
        """Test calculating days difference with reversed dates."""
        start = datetime(2024, 1, 20, 9, 0, 0)
        end = datetime(2024, 1, 15, 9, 0, 0)

        result = ScheduleChain.calculate_days_difference(start, end)
        assert result == 5


class TestScheduleChainTimezones:
    """Test cases for timezone handling."""

    def test_different_timezone_conversion(self):
        """Test that times are properly converted to chain's timezone."""
        chain = ScheduleChain(name="test_chain", timezone_="America/New_York")

        # Create a time in UTC
        utc_time = datetime(2024, 1, 15, 17, 0, 0, tzinfo=ZoneInfo("UTC"))

        # Get steps (which converts to chain's timezone internally)
        # The conversion should happen in _get_steps
        steps = chain._get_steps(utc_time)

        # Just verify it doesn't crash and returns a list
        assert isinstance(steps, list)

    def test_timezone_aware_comparison(self):
        """Test that timezone-aware times work correctly."""
        chain = ScheduleChain(name="test_chain", timezone_="Europe/London")

        # Use actual current time since _within_shift_time uses datetime.now()
        now = datetime.now(ZoneInfo("Europe/London"))
        current_dow = (now.weekday() + 1) % 7
        current_hour = now.hour
        start_time = f"{current_hour:02d}:00"

        # Create schedule in London time
        schedule = [
            ScheduleEntry(
                matcher=ScheduleMatcherExpression(
                    start_day_expr="dow",
                    start_day_values=[current_dow],
                    start_time=start_time,
                    duration="2h"
                ),
                steps=[SimpleChainStep(user="test_user")]
            )
        ]

        chain.schedule = schedule
        steps = chain._get_steps(now)

        assert len(steps) == 1
        assert steps[0].user == "test_user"


class TestScheduleChainEdgeCases:
    """Test cases for edge cases and boundary conditions."""

    def test_midnight_shift(self):
        """Test shift that starts at midnight."""
        test_time = datetime(2024, 1, 15, 0, 30, 0, tzinfo=ZoneInfo("UTC"))

        shift_start, shift_end = ScheduleChain._get_shift_time("00:00", "8h", test_time)

        assert shift_start.hour == 0
        assert shift_start.minute == 0
        assert shift_end.hour == 8

    def test_shift_spanning_midnight(self):
        """Test shift that spans across midnight."""
        test_time = datetime(2024, 1, 15, 20, 0, 0, tzinfo=ZoneInfo("UTC"))

        shift_start, shift_end = ScheduleChain._get_shift_time("18:00", "8h", test_time)

        assert shift_start.hour == 18
        # Shift goes from 18:00 to 02:00 next day
        assert shift_end.day == 16
        assert shift_end.hour == 2

    def test_very_short_duration(self):
        """Test with very short duration."""
        test_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=ZoneInfo("UTC"))

        shift_start, shift_end = ScheduleChain._get_shift_time("12:00", "1m", test_time)

        assert shift_end - shift_start == timedelta(minutes=1)

    def test_very_long_duration(self):
        """Test with very long duration."""
        test_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=ZoneInfo("UTC"))

        shift_start, shift_end = ScheduleChain._get_shift_time("12:00", "7d", test_time)

        assert shift_end - shift_start == timedelta(days=7)

    def test_empty_start_day_values(self):
        """Test with empty start_day_values list."""
        chain = ScheduleChain(name="test_chain", timezone_="UTC")
        test_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=ZoneInfo("UTC"))

        result = chain._match_day_condition("dow", [], test_time)
        assert result is False
