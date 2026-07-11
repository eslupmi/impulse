import pytest
from fastapi import HTTPException

from app.maintenance.api import (
    owner_id_from_payload,
    validate_owner_id,
    window_from_ws_item,
    windows_from_ws_payload,
)


def _window_payload(**overrides):
    payload = {
        "id": "w1",
        "start": "2026-06-11T19:00:00+00:00",
        "end": "2026-06-11T20:00:00+00:00",
        "matchers": ['service="test"'],
        "comment": "Network maintenance",
        "owner_id": "U123",
    }
    payload.update(overrides)
    return payload


ASSIGNABLE = {"U123", "U555"}


def test_owner_id_from_payload_uses_explicit_value():
    assert owner_id_from_payload({"owner_id": "U999"}) == "U999"


def test_owner_id_from_payload_required():
    with pytest.raises(HTTPException) as exc:
        owner_id_from_payload({})
    assert exc.value.detail == "owner_id is required"


def test_validate_owner_id_accepts_assignable_user():
    validate_owner_id("U123", ASSIGNABLE)


def test_validate_owner_id_preserves_existing_owner():
    validate_owner_id("U999", ASSIGNABLE, existing_owner_id="U999")


def test_validate_owner_id_rejects_unknown_owner():
    with pytest.raises(HTTPException) as exc:
        validate_owner_id("U999", ASSIGNABLE)
    assert exc.value.detail == "invalid owner_id"


def test_window_from_ws_item_includes_owner_id():
    window = window_from_ws_item(_window_payload(), assignable_user_ids=ASSIGNABLE)
    assert window["owner_id"] == "U123"


def test_window_from_ws_item_rejects_missing_owner():
    with pytest.raises(HTTPException) as exc:
        window_from_ws_item(_window_payload(owner_id=None), assignable_user_ids=ASSIGNABLE)
    assert exc.value.detail == "owner_id is required"


def test_window_from_ws_item_rejects_invalid_owner():
    payload = _window_payload(owner_id="U999")
    with pytest.raises(HTTPException) as exc:
        window_from_ws_item(payload, assignable_user_ids=ASSIGNABLE)
    assert exc.value.detail == "invalid owner_id"


def test_window_from_ws_item_allows_existing_owner_not_assignable():
    window = window_from_ws_item(
        _window_payload(owner_id="U999"),
        assignable_user_ids=ASSIGNABLE,
        existing_owner_id="U999",
    )
    assert window["owner_id"] == "U999"


def test_windows_from_ws_payload_validates_list():
    windows = windows_from_ws_payload(
        [_window_payload()],
        assignable_user_ids=ASSIGNABLE,
        existing_by_id={},
    )
    assert len(windows) == 1
    assert windows[0]["owner_id"] == "U123"


def test_windows_from_ws_payload_uses_existing_by_id():
    existing_by_id = {"w1": {"id": "w1", "owner_id": "U999"}}
    windows = windows_from_ws_payload(
        [_window_payload(owner_id="U999")],
        assignable_user_ids=ASSIGNABLE,
        existing_by_id=existing_by_id,
    )
    assert windows[0]["owner_id"] == "U999"
