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
            if 'matchers' in entry:
                if self._match_conditions(entry['matchers'], current_time):
                    return entry['steps']
            else:
                return entry['steps']
        return []

    def _match_conditions(self, conditions: List[Dict], current_time: datetime) -> bool:
        """
        Check each condition in the list against the current date and time.
        """
        for condition in conditions:
            try:
                start_day = condition['start_day']
                start_time = condition.get('start_time')
                duration = self._get_duration(condition)

                day_condition = self._check_day_condition(start_day, current_time)

                if start_time and duration:
                    if day_condition:
                        if self._within_shift_time(start_time, duration, current_time):
                            return True
                        else:
                            continue
                    else:
                        shift_start, shift_end = self._get_shift_time(start_time, duration, current_time)
                        days_difference = self.calculate_days_difference(shift_start, shift_end)
                        if days_difference < 1:
                            continue
                        else:
                            for i in range(days_difference + 1):
                                check_time = current_time - timedelta(days=i)
                                if self._check_day_condition(start_day, check_time):
                                    return self._within_shift_time(start_time, duration, check_time)

                if day_condition:
                    return True
            except Exception as e:
                logger.error(f"Failed to evaluate condition {condition}: {e}")
                return False

        return False

    def _check_day_condition(self, start_day: str, current_time: datetime) -> bool:
        """
        Check if the day condition is met.
        """
        dow = (current_time.weekday() + 1) % 7
        dom = current_time.day
        dow_str = self.DAY_MAP[dow]
        doe = int(current_time.timestamp() // (24 * 60 * 60))
        date_str = current_time.strftime("%Y-%m-%d")

        if "dow" in start_day:
            return self._match_dow_condition(start_day, dow)
        elif "doe" in start_day:
            return self._match_doe_condition(start_day, doe)
        elif "dom" in start_day:
            return self._match_dom_condition(start_day, dom)
        elif "date" in start_day:
            return self._match_date_condition(start_day, date_str)
        elif "=~" in start_day:
            return self._match_regex_condition(start_day, dow_str, doe, date_str)
        else:
            return self._evaluate_custom_expression(start_day)

    def _within_shift_time(self, start_time: str, duration: str, current_time: datetime) -> bool:
        """
        Check if the current time falls within the specified shift window.
        """
        shift_start, shift_end = self._get_shift_time(start_time, duration, current_time)

        return shift_start <= datetime.now().astimezone(self.tz) < shift_end

    @staticmethod
    def _get_duration(condition: dict) -> Optional[str]:
        """
        Get the duration from the condition.
        """
        duration = condition.get('duration')
        if duration:
            delta = unix_sleep_to_timedelta(duration)
            if delta > timedelta(days=1):
                logger.warning(f'Duration is greater than 1 day: {duration} for condition {condition}. Resetting to 24 hours.')
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
    def _match_regex_condition(start_day: str, dow_str: str, doe: int, date_str: str) -> bool:
        """
        Evaluate regex-based conditions with "=~" operator.
        """
        left, pattern = start_day.split("=~")
        left = left.strip()
        pattern = pattern.strip().strip('"')

        if left == "dow":
            target = dow_str
        elif left == "doe":
            target = str(doe)
        elif left == "date":
            target = date_str
        else:
            try:
                target = str(eval(left, {"__builtins__": {}}, {}))
            except Exception as e:
                logger.error(f"Failed to evaluate left side of regex condition {start_day}: {e}")
                return False

        try:
            return bool(re.search(pattern, target))
        except re.error as e:
            logger.error(f"Regex error in pattern {pattern}: {e}")
            return False

    @staticmethod
    def _match_dom_condition(start_day: str, dom: int) -> bool:
        """
        Evaluate day of the month conditions.
        """
        try:
            condition = start_day.replace("dom", str(dom))
            return eval(condition, {"__builtins__": {}}, {})
        except Exception as e:
            logger.error(f"Failed to evaluate DOM condition {start_day}: {e}")
            return False

    @staticmethod
    def _match_dow_condition(start_day: str, dow: int) -> bool:
        """
        Evaluate day of the week conditions.
        """
        try:
            condition = start_day.replace("dow", str(dow))
            return eval(condition, {"__builtins__": {}}, {})
        except Exception as e:
            logger.error(f"Failed to evaluate DOW condition {start_day}: {e}")
            return False

    @staticmethod
    def _match_doe_condition(start_day: str, doe: int) -> bool:
        """
        Evaluate day of epoch conditions.
        """
        try:
            condition = start_day.replace("doe", str(doe))
            return eval(condition, {"__builtins__": {}}, {})
        except Exception as e:
            logger.error(f"Failed to evaluate DOE condition {start_day}: {e}")
            return False

    @staticmethod
    def _match_date_condition(start_day: str, date_str: str) -> bool:
        """
        Evaluate specific date conditions.
        """
        try:
            condition = start_day.replace("date", f'"{date_str}"')
            return eval(condition, {"__builtins__": {}}, {})
        except Exception as e:
            logger.error(f"Failed to evaluate date condition {start_day}: {e}")
            return False

    @staticmethod
    def _evaluate_custom_expression(start_day: str) -> bool:
        """
        Evaluate any custom expression not directly tied to dow, doe, or date.
        """
        try:
            return eval(start_day, {"__builtins__": {}}, {})
        except Exception as e:
            logger.error(f"Failed to evaluate custom expression {start_day}: {e}")
            return False

    @staticmethod
    def calculate_days_difference(start_datetime: datetime, end_datetime: datetime) -> int:
        if start_datetime > end_datetime:
            start_datetime, end_datetime = end_datetime, start_datetime

        days_difference = (end_datetime.date() - start_datetime.date()).days

        return days_difference
