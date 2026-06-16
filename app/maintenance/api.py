from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request

from app.maintenance.models import MaintenanceWindow, _ensure_utc, _parse_iso
from app.route.matcher import Matcher


def parse_iso_to_utc(value: str) -> datetime:
    try:
        return _ensure_utc(_parse_iso(value.strip()))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid datetime: {value}") from exc


def matchers_from_payload(payload: dict) -> list:
    raw = payload.get("matchers")
    if not isinstance(raw, list):
        raise HTTPException(status_code=400, detail="matchers are required")
    items = [str(m).strip() for m in raw if str(m).strip()]
    if not items:
        raise HTTPException(status_code=400, detail="matchers are required")
    for m in items:
        try:
            Matcher(m)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid matcher: {m}") from exc
    return items


def window_from_payload(payload: dict, window_id: str = None) -> MaintenanceWindow:
    if "start" not in payload or "durationMs" not in payload:
        raise HTTPException(status_code=400, detail="start and durationMs are required")
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
    await request.app.state.maintenance_manager.reconcile_all()
