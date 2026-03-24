import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

from icalendar import Calendar, Event
from dateutil.rrule import rrulestr

from app.logging import logger


def _chain_name_to_filename(chain_name: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in (chain_name or ""))
    return (safe.strip("_") or "chain") + ".ics"


class ManagedChainsStore:
    MANAGED_CHAINS_DIR = "data/managed_chains"

    def __init__(self):
        self._ensure_directory_exists()

    def _ensure_directory_exists(self) -> None:
        if not os.path.exists(self.MANAGED_CHAINS_DIR):
            os.makedirs(self.MANAGED_CHAINS_DIR)
            logger.info("Created managed_chains directory", extra={"path": self.MANAGED_CHAINS_DIR})

    def _calendar_path(self, chain_name: str) -> str:
        return os.path.join(self.MANAGED_CHAINS_DIR, _chain_name_to_filename(chain_name))

    def load_chains(self, chain_name: str) -> List[Dict[str, Any]]:
        if not chain_name:
            return []
        path = self._calendar_path(chain_name)
        if not os.path.exists(path):
            return []

        try:
            with open(path, "rb") as f:
                cal = Calendar.from_ical(f.read())

            chains = []
            for component in cal.walk():
                if component.name == "VEVENT":
                    chain = self._ical_event_to_chain(component)
                    if chain:
                        chains.append(chain)

            logger.debug("Loaded managed chains", extra={"chain": chain_name, "count": len(chains)})
            return chains
        except Exception as e:
            logger.error("Failed to load managed chains", extra={"error": str(e), "chain": chain_name})
            return []

    def get_steps_for_now(self, chain_name: str, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        chains = self.load_chains(chain_name)
        if not chains:
            return []

        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        active = []
        for chain in chains:
            if self._is_chain_active_now(chain, now):
                active.append(chain)

        if not active:
            return []

        active.sort(key=lambda c: c.get("priority", 2), reverse=True)
        steps = active[0].get("steps")
        return steps if isinstance(steps, list) else []

    def save_chains(self, chain_name: str, chains: List[Dict[str, Any]]) -> bool:
        if not chain_name:
            return False
        path = self._calendar_path(chain_name)
        try:
            cal = Calendar()
            cal.add("prodid", "-//IMPulse Managed Chains//impulse.calendar//EN")
            cal.add("version", "2.0")
            cal.add("calscale", "GREGORIAN")
            cal.add("method", "PUBLISH")

            for chain in chains:
                event = self._chain_to_ical_event(chain)
                if event:
                    cal.add_component(event)

            with open(path, "wb") as f:
                f.write(cal.to_ical())

            logger.debug("Saved managed chains", extra={"chain": chain_name, "count": len(chains)})
            return True
        except Exception as e:
            logger.error("Failed to save managed chains", extra={"error": str(e), "chain": chain_name})
            return False

    def _chain_to_ical_event(self, chain: Dict[str, Any]) -> Optional[Event]:
        try:
            event = Event()

            event.add("uid", chain.get("id", ""))
            event.add("summary", chain.get("title", "Managed Chain"))

            start = chain.get("start")
            if start:
                start_dt = self._parse_datetime(start)
                if start_dt:
                    event.add("dtstart", start_dt)

            end = chain.get("end")
            if end:
                end_dt = self._parse_datetime(end)
                if end_dt:
                    event.add("dtend", end_dt)

            event.add("dtstamp", datetime.now(timezone.utc))

            repeat = chain.get("repeat")
            if repeat:
                rrule = self._repeat_to_rrule(repeat)
                if rrule:
                    event.add("rrule", rrule)

            repeatEnd = chain.get("repeatEnd")
            if repeatEnd:
                repeatEnd_dt = self._parse_datetime(repeatEnd)
                if repeatEnd_dt:
                    event.add("x-repeat-end", repeatEnd_dt)

            steps = chain.get("steps")
            if steps:
                import json
                event.add("description", json.dumps(steps))

            priority = chain.get("priority")
            if priority is not None:
                event.add("x-priority", str(priority))

            return event
        except Exception as e:
            logger.error("Failed to convert chain to iCal event", extra={"error": str(e), "chain_id": chain.get("id")})
            return None

    def _ical_event_to_chain(self, event: Event) -> Optional[Dict[str, Any]]:
        try:
            chain = {}

            uid = event.get("uid")
            if uid:
                chain["id"] = str(uid)

            summary = event.get("summary")
            if summary:
                chain["title"] = str(summary)
            else:
                chain["title"] = ""

            dtstart = event.get("dtstart")
            if dtstart:
                dt = dtstart.dt if hasattr(dtstart, "dt") else dtstart
                if hasattr(dt, 'isoformat'):
                    iso_str = dt.isoformat()
                    if not iso_str.endswith('Z') and '+' not in iso_str and '-' not in iso_str[-6:]:
                        iso_str += 'Z'
                    chain["start"] = iso_str
                else:
                    chain["start"] = str(dt)

            dtend = event.get("dtend")
            if dtend:
                dt = dtend.dt if hasattr(dtend, "dt") else dtend
                if hasattr(dt, 'isoformat'):
                    iso_str = dt.isoformat()
                    if not iso_str.endswith('Z') and '+' not in iso_str and '-' not in iso_str[-6:]:
                        iso_str += 'Z'
                    chain["end"] = iso_str
                else:
                    chain["end"] = str(dt)
            else:
                chain["end"] = None

            rrule = event.get("rrule")
            if rrule:
                chain["repeat"] = self._rrule_to_repeat(rrule)
            else:
                chain["repeat"] = None

            x_repeat_end = event.get("x-repeat-end")
            if x_repeat_end:
                dt = x_repeat_end.dt if hasattr(x_repeat_end, "dt") else x_repeat_end
                if hasattr(dt, 'isoformat'):
                    iso_str = dt.isoformat()
                    if not iso_str.endswith('Z') and '+' not in iso_str and '-' not in iso_str[-6:]:
                        iso_str += 'Z'
                    chain["repeatEnd"] = iso_str
                else:
                    chain["repeatEnd"] = str(dt)
            else:
                chain["repeatEnd"] = None

            description = event.get("description")
            if description:
                import json
                try:
                    chain["steps"] = json.loads(str(description))
                except json.JSONDecodeError:
                    chain["steps"] = None
            else:
                chain["steps"] = None

            x_priority = event.get("x-priority")
            if x_priority:
                try:
                    chain["priority"] = int(str(x_priority))
                except (ValueError, TypeError):
                    chain["priority"] = None
            else:
                chain["priority"] = None

            return chain
        except Exception as e:
            logger.error("Failed to convert iCal event to chain", extra={"error": str(e)})
            return None

    def _parse_datetime(self, dt_str: str) -> Optional[datetime]:
        if isinstance(dt_str, datetime):
            return dt_str

        try:
            if dt_str.endswith("Z"):
                dt_str = dt_str[:-1] + "+00:00"
            return datetime.fromisoformat(dt_str)
        except Exception:
            try:
                return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S.%f%z")
            except Exception:
                return None

    def _is_chain_active_now(self, chain: Dict[str, Any], now: datetime) -> bool:
        start = self._parse_datetime(chain.get("start"))
        if start is None:
            return False
        end = self._parse_datetime(chain.get("end")) or (start + timedelta(days=1))
        repeat_end = self._parse_datetime(chain.get("repeatEnd")) if chain.get("repeatEnd") else None
        repeat = chain.get("repeat")

        if not repeat:
            return start <= now < end

        occurrence_start = start
        occurrence_end = end
        duration = end - start
        while occurrence_start <= now:
            if repeat_end and occurrence_end > repeat_end:
                return False
            if occurrence_start <= now < occurrence_end:
                return True
            occurrence_start = self._next_occurrence_start(start, occurrence_start, repeat)
            occurrence_end = occurrence_start + duration
        return False

    @staticmethod
    def _next_occurrence_start(base_start: datetime, current_start: datetime, repeat: str) -> datetime:
        if repeat == "daily":
            return current_start + timedelta(days=1)
        if repeat == "weekly":
            return current_start + timedelta(days=7)
        if repeat == "monthly":
            year = current_start.year + (1 if current_start.month == 12 else 0)
            month = 1 if current_start.month == 12 else current_start.month + 1
            day = min(base_start.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
            return current_start.replace(year=year, month=month, day=day)
        if repeat == "yearly":
            year = current_start.year + 1
            day = base_start.day
            month = base_start.month
            if month == 2 and day == 29 and not (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)):
                day = 28
            return current_start.replace(year=year, month=month, day=day)
        return current_start + timedelta(days=1)

    def _repeat_to_rrule(self, repeat: str) -> Optional[Dict]:
        repeat_map = {
            "daily": {"FREQ": "DAILY"},
            "weekly": {"FREQ": "WEEKLY"},
            "monthly": {"FREQ": "MONTHLY"},
            "yearly": {"FREQ": "YEARLY"},
        }
        return repeat_map.get(repeat.lower()) if repeat else None

    def _rrule_to_repeat(self, rrule) -> Optional[str]:
        if not rrule:
            return None

        freq = None
        if hasattr(rrule, "get"):
            freq_list = rrule.get("FREQ")
            if freq_list:
                freq = freq_list[0] if isinstance(freq_list, list) else freq_list
        elif hasattr(rrule, "to_ical"):
            rrule_str = rrule.to_ical().decode("utf-8")
            if "FREQ=DAILY" in rrule_str:
                return "daily"
            elif "FREQ=WEEKLY" in rrule_str:
                return "weekly"
            elif "FREQ=MONTHLY" in rrule_str:
                return "monthly"
            elif "FREQ=YEARLY" in rrule_str:
                return "yearly"

        if freq:
            freq_map = {
                "DAILY": "daily",
                "WEEKLY": "weekly",
                "MONTHLY": "monthly",
                "YEARLY": "yearly",
            }
            return freq_map.get(str(freq).upper())

        return None


managed_chains_store = ManagedChainsStore()
