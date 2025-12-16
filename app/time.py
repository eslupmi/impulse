from datetime import timedelta, datetime, timezone
import calendar


def unix_sleep_to_timedelta(unix_sleep_time):
    value = int(unix_sleep_time[:-1])
    unit = unix_sleep_time[-1]
    unit_map = {'s': 'seconds', 'm': 'minutes', 'h': 'hours', 'd': 'days'}
    return timedelta(**{unit_map[unit]: value})


def _add_months(source_date: datetime, months: int) -> datetime:
    """
    Add months to a datetime without external dependencies.
    Handles edge cases like month-end dates gracefully.
    
    Args:
        source_date: The starting datetime
        months: Number of months to add
        
    Returns:
        datetime: The resulting datetime
    """
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1
    day = min(source_date.day, calendar.monthrange(year, month)[1])
    return source_date.replace(year=year, month=month, day=day)


def calculate_freeze_time(option: str, general_config) -> datetime:
    """
    Calculate freeze expiration datetime based on the option selected.
    
    Args:
        option: One of 'tomorrow', 'next_monday', 'month', '6months'
        general_config: GeneralConfig object with workday_start and week_start
        
    Returns:
        datetime: The calculated freeze expiration time
    """
    now = datetime.now(timezone.utc)
    workday_start_parts = general_config.workday_start.split(':')
    workday_hour = int(workday_start_parts[0])
    workday_minute = int(workday_start_parts[1])
    
    if option == 'tomorrow':
        # Tomorrow at workday_start
        freeze_time = now + timedelta(days=1)
        freeze_time = freeze_time.replace(hour=workday_hour, minute=workday_minute, second=0, microsecond=0)
        return freeze_time
        
    elif option == 'next_monday':
        # Next Monday at workday_start
        # Convert week_start to weekday number
        week_start_map = {
            'Mon': 0, '1': 0,
            'Tue': 1, '2': 1,
            'Wed': 2, '3': 2,
            'Thu': 3, '4': 3,
            'Fri': 4, '5': 4,
            'Sat': 5, '6': 5,
            'Sun': 6, '0': 6, '7': 6
        }
        target_weekday = week_start_map.get(general_config.week_start, 0)  # Default to Monday
        
        days_ahead = target_weekday - now.weekday()
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
            
        freeze_time = now + timedelta(days=days_ahead)
        freeze_time = freeze_time.replace(hour=workday_hour, minute=workday_minute, second=0, microsecond=0)
        return freeze_time
        
    elif option == 'month':
        # Same day next month at workday_start
        freeze_time = _add_months(now, 1)
        freeze_time = freeze_time.replace(hour=workday_hour, minute=workday_minute, second=0, microsecond=0)
        return freeze_time
        
    elif option == '6months':
        # Same day in 6 months at workday_start
        freeze_time = _add_months(now, 6)
        freeze_time = freeze_time.replace(hour=workday_hour, minute=workday_minute, second=0, microsecond=0)
        return freeze_time
        
    else:
        raise ValueError(f"Unknown freeze option: {option}")


def format_freeze_expiration(frozen_until: datetime) -> str:
    """
    Format freeze expiration time for button text.
    
    Args:
        frozen_until: The datetime when freeze expires
        
    Returns:
        str: Formatted string like "Mon 9:00" or "Aug 13"
    """
    now = datetime.now(timezone.utc)
    time_diff = frozen_until - now
    
    if time_diff.days < 7:
        # Less than a week: show day and time like "Mon 9:00"
        day_name = frozen_until.strftime('%a')
        time_str = frozen_until.strftime('%H:%M')
        return f"{day_name} {time_str}"
    else:
        # More than a week: show month and day like "Aug 13"
        return frozen_until.strftime('%b %d')


def parse_week_start_to_weekday(week_start: str) -> int:
    """
    Convert week_start string to Python weekday number (0=Monday, 6=Sunday).
    
    Args:
        week_start: Week start string (e.g., 'Mon', '1', etc.)
        
    Returns:
        int: Weekday number (0-6)
    """
    week_start_map = {
        'Mon': 0, '1': 0,
        'Tue': 1, '2': 1,
        'Wed': 2, '3': 2,
        'Thu': 3, '4': 3,
        'Fri': 4, '5': 4,
        'Sat': 5, '6': 5,
        'Sun': 6, '0': 6, '7': 6
    }
    return week_start_map.get(week_start, 0)
