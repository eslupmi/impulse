import calendar
from datetime import timedelta, datetime, timezone
from zoneinfo import ZoneInfo


def unix_sleep_to_timedelta(unix_sleep_time):
    value = int(unix_sleep_time[:-1])
    unit = unix_sleep_time[-1]
    unit_map = {'s': 'seconds', 'm': 'minutes', 'h': 'hours', 'd': 'days'}
    return timedelta(**{unit_map[unit]: value})


def _add_months(source_date: datetime, months: int) -> datetime:
    month = source_date.month - 1 + months
    year = source_date.year + month // 12
    month = month % 12 + 1
    day = min(source_date.day, calendar.monthrange(year, month)[1])
    return source_date.replace(year=year, month=month, day=day)


def calculate_freeze_time(option: str, general_config, timezone_str: str = "UTC") -> datetime:
    tz = ZoneInfo(timezone_str)
    now = datetime.now(tz)
    workday_start_parts = general_config.workday_start.split(':')
    workday_hour = int(workday_start_parts[0])
    workday_minute = int(workday_start_parts[1])
    
    if option == 'tomorrow':
        freeze_time = now + timedelta(days=1)
        freeze_time = freeze_time.replace(hour=workday_hour, minute=workday_minute, second=0, microsecond=0)
        return freeze_time.astimezone(timezone.utc)
        
    elif option == 'next_monday':
        week_start_map = {
            'Mon': 0, '1': 0,
            'Tue': 1, '2': 1,
            'Wed': 2, '3': 2,
            'Thu': 3, '4': 3,
            'Fri': 4, '5': 4,
            'Sat': 5, '6': 5,
            'Sun': 6, '0': 6, '7': 6
        }
        target_weekday = week_start_map.get(general_config.week_start, 0)
        
        days_ahead = target_weekday - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
            
        freeze_time = now + timedelta(days=days_ahead)
        freeze_time = freeze_time.replace(hour=workday_hour, minute=workday_minute, second=0, microsecond=0)
        return freeze_time.astimezone(timezone.utc)
        
    elif option == 'month':
        freeze_time = _add_months(now, 1)
        freeze_time = freeze_time.replace(hour=workday_hour, minute=workday_minute, second=0, microsecond=0)
        return freeze_time.astimezone(timezone.utc)
        
    elif option == '6months':
        freeze_time = _add_months(now, 6)
        freeze_time = freeze_time.replace(hour=workday_hour, minute=workday_minute, second=0, microsecond=0)
        return freeze_time.astimezone(timezone.utc)
        
    else:
        raise ValueError(f"Unknown freeze option: {option}")


def format_freeze_expiration(frozen_until: datetime, tz_str: str = "UTC") -> str:
    tz = ZoneInfo(tz_str)
    now = datetime.now(tz)
    frozen_until_local = frozen_until.astimezone(tz)
    time_diff = frozen_until_local - now
    
    if time_diff.days < 7:
        day_name = frozen_until_local.strftime('%a')
        time_str = frozen_until_local.strftime('%H:%M')
        return f"{day_name} {time_str}"
    else:
        return frozen_until_local.strftime('%b %d')


def parse_week_start_to_weekday(week_start: str) -> int:
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
