from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, Request

from app.maintenance.models import MaintenanceWindow, _ensure_utc, _parse_iso
from app.maintenance.store import get_maintenance_store
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


def _acting_user_label(acting_user: Optional[dict]) -> Optional[str]:
    if not acting_user:
        return None
    return (
        acting_user.get("username")
        or acting_user.get("full_name")
        or str(acting_user.get("id") or "")
    ) or None


def window_from_ws_item(payload: dict) -> dict:
    if "start" not in payload or "end" not in payload:
        raise HTTPException(status_code=400, detail="start and end are required")
    starts_at = parse_iso_to_utc(payload["start"])
    ends_at = parse_iso_to_utc(payload["end"])
    if ends_at <= starts_at:
        raise HTTPException(status_code=400, detail="end must be after start")

    matchers = matchers_from_payload(payload)
    comment = str(payload.get("comment", "") or "").strip()
    if not comment:
        raise HTTPException(status_code=400, detail="comment is required")

    window_id = payload.get("id")
    if not window_id:
        raise HTTPException(status_code=400, detail="id is required")

    return {
        "id": str(window_id),
        "start": starts_at.astimezone(timezone.utc).isoformat(),
        "end": ends_at.astimezone(timezone.utc).isoformat(),
        "matchers": matchers,
        "comment": comment,
        "created_by": payload.get("created_by"),
    }


def windows_from_ws_payload(
    data: list,
    acting_user: Optional[dict],
    existing_by_id: Optional[Dict[str, dict]] = None,
) -> List[Dict[str, Any]]:
    if not isinstance(data, list):
        raise HTTPException(status_code=400, detail="data must be a list")

    existing_by_id = existing_by_id or {}
    user_label = _acting_user_label(acting_user)
    windows = []

    for item in data:
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail="each window must be an object")
        window = window_from_ws_item(item)
        prev = existing_by_id.get(window["id"])
        if prev and prev.get("created_by"):
            window["created_by"] = prev["created_by"]
        elif not window.get("created_by"):
            window["created_by"] = user_label
        windows.append(window)

    return windows


def removed_windows(existing: List[Dict[str, Any]], saved: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    saved_ids = {w["id"] for w in saved}
    return [w for w in existing if w["id"] not in saved_ids]


async def reconcile_maintenance(request: Request):
    await request.app.state.maintenance_manager.reconcile_all()


def merge_and_validate_save(data: list, acting_user: Optional[dict]) -> List[Dict[str, Any]]:
    store = get_maintenance_store()
    existing_by_id = {w["id"]: w for w in store.load_windows()}
    return windows_from_ws_payload(data, acting_user, existing_by_id)
