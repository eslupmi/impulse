from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request

from app.maintenance.models import MaintenanceWindow, split_matcher_clauses
from app.route.matcher import Matcher


def parse_iso_to_utc(value: str) -> datetime:
    s = value.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid datetime: {value}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def matchers_from_payload(payload: dict) -> list:
    raw = payload.get("matchers")
    if isinstance(raw, list):
        items = [str(m).strip() for m in raw if str(m).strip()]
    elif isinstance(raw, str):
        items = split_matcher_clauses(raw)
    else:
        items = []
    if not items:
        raise HTTPException(status_code=400, detail="matchers are required")
    for m in items:
        try:
            Matcher(m)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid matcher: {m}") from exc
    return items


def window_from_payload(payload: dict, window_id: str = None) -> MaintenanceWindow:
    if "starts_at" in payload and "ends_at" in payload:
        starts_at = parse_iso_to_utc(payload["starts_at"])
        ends_at = parse_iso_to_utc(payload["ends_at"])
    else:
        if "start" not in payload or "durationMs" not in payload:
            raise HTTPException(status_code=400, detail="starts_at/ends_at or start/durationMs are required")
        starts_at = parse_iso_to_utc(payload["start"])
        try:
            duration_ms = int(payload["durationMs"])
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="durationMs must be an integer") from exc
        if duration_ms <= 0:
            raise HTTPException(status_code=400, detail="durationMs must be positive")
        ends_at = starts_at + timedelta(milliseconds=duration_ms)

    if ends_at <= starts_at:
        raise HTTPException(status_code=400, detail="ends_at must be after starts_at")

    matchers = matchers_from_payload(payload)
    comment = str(payload.get("comment", "") or "")
    kwargs = {
        "starts_at": starts_at,
        "ends_at": ends_at,
        "matchers": matchers,
        "comment": comment,
    }
    if window_id:
        kwargs["id"] = window_id
    return MaintenanceWindow(**kwargs)


def serialize_window(w: MaintenanceWindow) -> dict:
    return {
        "id": w.id,
        "starts_at": w.starts_at.astimezone(timezone.utc).isoformat(),
        "ends_at": w.ends_at.astimezone(timezone.utc).isoformat(),
        "matchers": list(w.matchers),
        "comment": w.comment,
        "created_by": w.created_by,
    }


async def reconcile_maintenance(request: Request):
    manager = getattr(request.app.state, "maintenance_manager", None)
    if manager is not None:
        await manager.reconcile_active_incidents()
