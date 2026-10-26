import pytest
from fastapi import HTTPException

from app.maintenance.api import (
    validate_owner_id,
    window_from_ws_item,
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
    payload = _window_payload(owner_id=None)
    with pytest.raises(HTTPException) as exc:
        window_from_ws_item(payload, assignable_user_ids=ASSIGNABLE)
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


def test_window_from_ws_item_rejects_list():
    payload = [_window_payload()]
    with pytest.raises(HTTPException) as exc:
        window_from_ws_item(payload, assignable_user_ids=ASSIGNABLE)
    assert exc.value.detail == "window must be an object"
