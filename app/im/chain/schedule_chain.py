import re
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from zoneinfo import ZoneInfo

from app.logging import logger
from app.time import unix_sleep_to_timedelta


class ScheduleChain:
    DAY_MAP = {0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}
    DEFAULT_TIMEZONE = "UTC"

    def __init__(self, name, timezone: str = DEFAULT_TIMEZONE, schedule: List[Dict] = None):
        self.name = name
        self.timezone = timezone or self.DEFAULT_TIMEZONE
        self.schedule = schedule if schedule else []
        self.tz = ZoneInfo(self.timezone)

    def __repr__(self):
        return self.name

    @property
    def steps(self) -> List[Dict]:
        """
        Get the steps for the current time.
        """
        current_time = datetime.now()
        return self._get_steps(current_time)

    def _get_steps(self, current_time: datetime) -> List[Dict]:
        """
        Get the steps based on the matchers and schedule.
        """
        current_time = current_time.astimezone(self.tz)

        for entry in self.schedule:
            if 'matcher' in entry:
                if self._match_conditions(entry['matcher'], current_time):
                    return entry['steps']
            else:
                return entry['steps']
        return []

    def _match_conditions(self, matcher, current_time: datetime) -> bool:
        """
        Check each condition in the list against the current date and time.
        """
        start_day_expr = matcher.get('start_day_expr')
        start_day_values = matcher.get('start_day_values')
        start_time = matcher.get('start_time')
        duration = matcher.get('duration')

        duration_ = self._get_duration(duration)
        day_condition = self._check_day_condition(start_day_expr, start_day_values, current_time)

        if start_time and duration_:
            if day_condition:
                if self._within_shift_time(start_time, duration_, current_time):
                    return True
                else:
                    return False
            else:
                shift_start, shift_end = self._get_shift_time(start_time, duration_, current_time)
                days_difference = self.calculate_days_difference(shift_start, shift_end)
                if days_difference < 1:
                    return False
                else:
                    for i in range(days_difference + 1):
                        check_time = current_time - timedelta(days=i)
                        if self._check_day_condition(start_day_expr, start_day_values, check_time):
                            return self._within_shift_time(start_time, duration_, check_time)

        if day_condition:
            return True

        return False

    def _check_day_condition(self, start_day_expr: str, start_day_values: List, current_time: datetime) -> bool:
        """
        Check if the day condition is met.
        """
        now = {
            'dow': (current_time.weekday() + 1) % 7,
            'dom': current_time.day,
            'date': current_time.strftime("%Y-%m-%d"),
        }

        expr = re.compile(r'(?P<selector>dow|dom|date)(\s?%\s?(?P<divider>\d))?')
        match = expr.match(start_day_expr)
        if not match:
            logger.error(f'Incorrect start_day_expr \'{start_day_expr}\'')

        selector = match.group('selector')
        divider = match.group('divider')

        value = now[selector]
        if divider is not None:
            value = value % divider

        if selector == 'dow':
            return self._match_dow_condition(value, start_day_values)
        elif selector == "dom":
            return self._match_dom_condition(value, start_day_values)
        elif selector == "date":
            return self._match_date_condition(value, start_day_values)

    def _within_shift_time(self, start_time: str, duration: str, current_time: datetime) -> bool:
        """
        Check if the current time falls within the specified shift window.
        """
        shift_start, shift_end = self._get_shift_time(start_time, duration, current_time)
        return shift_start <= datetime.now().astimezone(self.tz) < shift_end

    @staticmethod
    def _get_duration(duration: str) -> Optional[str]:
        """
        Get the duration from the condition.
        """
        if duration:
            delta = unix_sleep_to_timedelta(duration)
            if delta > timedelta(days=1):
                logger.warning(f'Schedule chain matcher duration \'{duration}\' greater than 24h. Resetting to 24 hours.')
                return '24h'
            return duration

    @staticmethod
    def _get_shift_time(start_time: str, duration: str, current_time: datetime) -> Tuple[datetime, datetime]:
        """
        Get the start and end time of the shift.
        """
        start_hour, start_minute = map(int, start_time.split(":"))
        shift_start = current_time.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
        shift_end = shift_start + unix_sleep_to_timedelta(duration)

        return shift_start, shift_end

    @staticmethod
    def _match_dow_condition(value: int, start_day_values: List) -> bool:
        """
        Evaluate day of the week conditions.
        """
        for i in start_day_values:
            if value == i or ScheduleChain.DAY_MAP[value] == i:
                return True
        return False

    @staticmethod
    def _match_dom_condition(value: int, start_day_values: List) -> bool:
        """
        Evaluate day of the month conditions.
        """
        if value in start_day_values:
            return True
        return False

    @staticmethod
    def _match_date_condition(value: str, start_day_values: List) -> bool:
        """
        Evaluate specific date conditions.
        """
        if value in start_day_values:
            return True
        return False

    @staticmethod
    def calculate_days_difference(start_datetime: datetime, end_datetime: datetime) -> int:
        if start_datetime > end_datetime:
            start_datetime, end_datetime = end_datetime, start_datetime
        days_difference = (end_datetime.date() - start_datetime.date()).days
        return days_difference
