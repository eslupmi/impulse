from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import HTTPException, Request

from app.maintenance.models import _ensure_utc, _parse_iso
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
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return items


def validate_owner_id(
    owner_id: str,
    assignable_user_ids: Set[str],
    existing_owner_id: Optional[str] = None,
) -> None:
    if owner_id in assignable_user_ids:
        return
    if existing_owner_id and owner_id == str(existing_owner_id):
        return
    raise HTTPException(status_code=400, detail="invalid owner_id")


def owner_id_from_payload(
    payload: dict,
    acting_user: Optional[dict],
    assignable_user_ids: Optional[Set[str]] = None,
) -> str:
    owner_id = payload.get("owner_id")
    if owner_id:
        return str(owner_id)
    acting_id = (acting_user or {}).get("id")
    if acting_id:
        resolved = str(acting_id)
        if assignable_user_ids is not None and resolved not in assignable_user_ids:
            raise HTTPException(status_code=400, detail="owner_id is required")
        return resolved
    raise HTTPException(status_code=400, detail="owner_id is required")


def window_from_ws_item(
    payload: dict,
    acting_user: Optional[dict] = None,
    assignable_user_ids: Optional[Set[str]] = None,
    existing_owner_id: Optional[str] = None,
) -> dict:
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

    owner_id = owner_id_from_payload(payload, acting_user, assignable_user_ids)
    if assignable_user_ids is not None:
        validate_owner_id(owner_id, assignable_user_ids, existing_owner_id)

    return {
        "id": str(window_id),
        "start": starts_at.astimezone(timezone.utc).isoformat(),
        "end": ends_at.astimezone(timezone.utc).isoformat(),
        "matchers": matchers,
        "comment": comment,
        "owner_id": owner_id,
    }


def windows_from_ws_payload(
    data: list,
    acting_user: Optional[dict],
    assignable_user_ids: Optional[Set[str]] = None,
    existing_by_id: Optional[Dict[str, dict]] = None,
) -> List[Dict[str, Any]]:
    if not isinstance(data, list):
        raise HTTPException(status_code=400, detail="data must be a list")

    existing_by_id = existing_by_id or {}
    windows = []

    for item in data:
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail="each window must be an object")
        window_id = item.get("id")
        prev = existing_by_id.get(str(window_id), {})
        windows.append(window_from_ws_item(
            item,
            acting_user,
            assignable_user_ids,
            prev.get("owner_id"),
        ))

    return windows


def removed_windows(existing: List[Dict[str, Any]], saved: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    saved_ids = {w["id"] for w in saved}
    return [w for w in existing if w["id"] not in saved_ids]


async def reconcile_maintenance(request: Request):
    await request.app.state.maintenance_manager.reconcile_all()


def merge_and_validate_save(
    data: list,
    acting_user: Optional[dict],
    assignable_user_ids: Set[str],
    existing_by_id: Dict[str, dict],
) -> List[Dict[str, Any]]:
    return windows_from_ws_payload(data, acting_user, assignable_user_ids, existing_by_id)
