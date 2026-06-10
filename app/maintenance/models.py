import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from app.route.matcher import Matcher


def split_matcher_clauses(s: str) -> List[str]:
    """Split a comma-separated matcher string respecting quoted values."""
    parts: List[str] = []
    buf: List[str] = []
    in_quote = False
    quote_char = ""
    for ch in s or "":
        if in_quote:
            buf.append(ch)
            if ch == quote_char:
                in_quote = False
        elif ch in ('"', "'"):
            in_quote = True
            quote_char = ch
            buf.append(ch)
        elif ch == ",":
            part = "".join(buf).strip()
            if part:
                parts.append(part)
            buf = []
        else:
            buf.append(ch)
    last = "".join(buf).strip()
    if last:
        parts.append(last)
    return parts


@dataclass
class MaintenanceWindow:
    starts_at: datetime
    ends_at: datetime
    matchers: List[str]
    comment: str = ""
    created_by: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        self.starts_at = _ensure_utc(self.starts_at)
        self.ends_at = _ensure_utc(self.ends_at)
        self._compiled: List[Matcher] = [Matcher(m) for m in self.matchers]

    @property
    def compiled_matchers(self) -> List[Matcher]:
        return self._compiled

    def is_active(self, now: datetime) -> bool:
        return self.starts_at <= now < self.ends_at

    def matches_incident(self, incident) -> bool:
        if not self._compiled:
            return False
        return all(m.matches(incident.payload) for m in self._compiled)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "starts_at": self.starts_at.isoformat(),
            "ends_at": self.ends_at.isoformat(),
            "matchers": list(self.matchers),
            "comment": self.comment,
            "created_by": self.created_by,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MaintenanceWindow":
        return cls(
            starts_at=_parse_iso(data["starts_at"]),
            ends_at=_parse_iso(data["ends_at"]),
            matchers=list(data.get("matchers", [])),
            comment=data.get("comment", ""),
            created_by=data.get("created_by"),
            id=data.get("id") or str(uuid.uuid4()),
        )


def _ensure_utc(value) -> datetime:
    if isinstance(value, str):
        value = _parse_iso(value)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_iso(value: str) -> datetime:
    s = value
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)
