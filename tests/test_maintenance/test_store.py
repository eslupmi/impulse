from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.config.validation import IncidentTimeouts
from app.maintenance.models import MaintenanceWindow
from app.maintenance.store import MaintenanceStore

ASSIGNABLE = {"U123"}


def _make_store(tmp_path: Path) -> MaintenanceStore:
    with patch("app.maintenance.store.get_environment_config") as mock_env:
        mock_env.return_value.data_path = str(tmp_path)
        return MaintenanceStore()


def _mock_closed_retention(closed: str = "7d"):
    timeouts = IncidentTimeouts(closed=closed)
    mock_config = patch("app.maintenance.store.get_config").start()
    mock_config.return_value.incident.timeouts = timeouts
    return mock_config


def _seed_windows(store: MaintenanceStore, windows: list[dict]) -> None:
    store._ensure_dir()
    assert store._write_windows_unlocked(windows) is True


def _sample_window(window_id: str = "w1") -> dict:
    now = datetime.now(timezone.utc)
    start = now + timedelta(hours=1)
    end = start + timedelta(hours=4)
    return {
        "id": window_id,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "matchers": ['service="postgres"'],
        "comment": "planned work",
        "owner_id": "U123",
    }


def test_store_uses_windows_ics(tmp_path: Path):
    store = _make_store(tmp_path)
    assert store._file == str(tmp_path / "maintenance" / "windows.ics")


def test_save_and_load_windows_round_trip(tmp_path: Path):
    store = _make_store(tmp_path)
    mock_config = _mock_closed_retention("7d")
    try:
        windows = [_sample_window("w1"), _sample_window("w2")]
        windows[1]["matchers"] = ['service="elastic"', 'env="prod"']
        windows[1]["id"] = "w2"

        assert store.upsert_window(windows[0], ASSIGNABLE)[0] is True
        assert store.upsert_window(windows[1], ASSIGNABLE)[0] is True
        loaded = store.load_windows()
        assert len(loaded) == 2
        by_id = {w["id"]: w for w in loaded}
        assert by_id["w1"]["comment"] == "planned work"
        assert by_id["w1"]["owner_id"] == "U123"
        assert by_id["w2"]["matchers"] == ['service="elastic"', 'env="prod"']
    finally:
        mock_config.stop()


def test_list_returns_maintenance_window_objects(tmp_path: Path):
    store = _make_store(tmp_path)
    mock_config = _mock_closed_retention("7d")
    try:
        assert store.upsert_window(_sample_window(), ASSIGNABLE)[0] is True
        windows = store.windows_list()
        assert len(windows) == 1
        assert isinstance(windows[0], MaintenanceWindow)
        assert windows[0].matchers == ['service="postgres"']
    finally:
        mock_config.stop()


def test_missing_ics_returns_empty_list(tmp_path: Path):
    store = _make_store(tmp_path)
    assert store.load_windows() == []


def test_prune_expired_windows(tmp_path: Path):
    store = _make_store(tmp_path)
    mock_config = _mock_closed_retention("7d")
    now = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)
    try:
        old = {
            "id": "old",
            "start": "2026-05-01T10:00:00+00:00",
            "end": "2026-05-01T12:00:00+00:00",
            "matchers": ['alertname="A"'],
            "comment": "old",
        }
        recent = _sample_window("recent")
        store._write_windows_unlocked([old, recent])

        removed = store.prune_expired_windows(now)
        assert removed == 1
        assert len(store.load_windows()) == 1
        assert store.load_windows()[0]["id"] == "recent"
    finally:
        mock_config.stop()


def test_upsert_retains_recently_ended_windows_until_closed_timeout(tmp_path: Path):
    store = _make_store(tmp_path)
    mock_config = _mock_closed_retention("7d")
    now = datetime.now(timezone.utc)
    try:
        recent = {
            "id": "recent-ended",
            "start": (now - timedelta(days=1, hours=2)).isoformat(),
            "end": (now - timedelta(days=1)).isoformat(),
            "matchers": ['alertname="A"'],
            "comment": "recent maintenance",
            "owner_id": "U123",
        }
        old = {
            "id": "old-ended",
            "start": (now - timedelta(days=8, hours=2)).isoformat(),
            "end": (now - timedelta(days=8)).isoformat(),
            "matchers": ['alertname="B"'],
            "comment": "old maintenance",
        }
        _seed_windows(store, [recent, old])
        ok, _existing, saved = store.upsert_window(recent, ASSIGNABLE)
        assert ok is True
        assert [window["id"] for window in saved] == ["recent-ended"]
    finally:
        mock_config.stop()


def test_skips_event_without_matchers(tmp_path: Path):
    store = _make_store(tmp_path)
    cal_path = store._file
    store._ensure_dir()
    with open(cal_path, "wb") as f:
        f.write(
            b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n"
            b"BEGIN:VEVENT\r\nUID:no-matchers\r\n"
            b"DTSTART:20260620T080000Z\r\nDTEND:20260620T120000Z\r\n"
            b"SUMMARY:test\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
        )
    assert store.load_windows() == []


def test_load_window_without_owner_id(tmp_path: Path):
    store = _make_store(tmp_path)
    store._ensure_dir()
    with open(store._file, "wb") as f:
        f.write(
            b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n"
            b"BEGIN:VEVENT\r\nUID:legacy\r\n"
            b"DTSTART:20260620T080000Z\r\nDTEND:20260620T120000Z\r\n"
            b"SUMMARY:test\r\n"
            b"X-MATCHER:alertname=\"A\"\r\n"
            b"END:VEVENT\r\nEND:VCALENDAR\r\n"
        )
    loaded = store.load_windows()
    assert len(loaded) == 1
    assert loaded[0]["id"] == "legacy"
    assert loaded[0]["owner_id"] is None


def test_upsert_window_keeps_ownerless_sibling(tmp_path: Path):
    store = _make_store(tmp_path)
    mock_config = _mock_closed_retention("7d")
    try:
        legacy = _sample_window("legacy")
        legacy["owner_id"] = None
        _seed_windows(store, [legacy])
        ok, _existing, _saved = store.upsert_window(_sample_window("new"), ASSIGNABLE)
        assert ok is True
        by_id = {w["id"]: w for w in store.load_windows()}
        assert by_id["legacy"]["owner_id"] is None
        assert by_id["new"]["owner_id"] == "U123"
        ics = Path(store._file).read_bytes()
        assert ics.count(b"X-OWNER-ID") == 1
        assert b"X-OWNER-ID:U123" in ics
    finally:
        mock_config.stop()


def test_delete_window_leaves_remaining(tmp_path: Path):
    store = _make_store(tmp_path)
    mock_config = _mock_closed_retention("7d")
    try:
        _seed_windows(store, [_sample_window("w1"), _sample_window("w2")])
        ok, _existing, _saved, deleted = store.delete_window("w1")
        assert ok is True
        assert deleted["id"] == "w1"
        assert [w["id"] for w in store.load_windows()] == ["w2"]
    finally:
        mock_config.stop()


def test_delete_missing_window_is_success(tmp_path: Path):
    store = _make_store(tmp_path)
    mock_config = _mock_closed_retention("7d")
    try:
        _seed_windows(store, [_sample_window("w1")])
        ok, _existing, _saved, deleted = store.delete_window("missing")
        assert ok is True
        assert deleted is None
        assert [w["id"] for w in store.load_windows()] == ["w1"]
    finally:
        mock_config.stop()


def test_upsert_drops_expired_siblings(tmp_path: Path):
    store = _make_store(tmp_path)
    mock_config = _mock_closed_retention("7d")
    now = datetime.now(timezone.utc)
    try:
        recent = {
            "id": "recent-ended",
            "start": (now - timedelta(days=1, hours=2)).isoformat(),
            "end": (now - timedelta(days=1)).isoformat(),
            "matchers": ['alertname="A"'],
            "comment": "recent maintenance",
        }
        old = {
            "id": "old-ended",
            "start": (now - timedelta(days=8, hours=2)).isoformat(),
            "end": (now - timedelta(days=8)).isoformat(),
            "matchers": ['alertname="B"'],
            "comment": "old maintenance",
        }
        store._write_windows_unlocked([recent, old])
        ok, _existing, saved = store.upsert_window(_sample_window("new"), ASSIGNABLE)
        assert ok is True
        assert {w["id"] for w in saved} == {"recent-ended", "new"}
    finally:
        mock_config.stop()


def test_upsert_rejects_invalid_payload_without_writing(tmp_path: Path):
    store = _make_store(tmp_path)
    legacy = _sample_window("legacy")
    legacy["owner_id"] = None
    _seed_windows(store, [legacy])
    before = Path(store._file).read_bytes()
    with pytest.raises(HTTPException) as exc:
        store.upsert_window(legacy, ASSIGNABLE)
    assert exc.value.detail == "owner_id is required"
    assert Path(store._file).read_bytes() == before
    loaded = store.load_windows()
    assert loaded[0]["id"] == "legacy"
    assert loaded[0]["owner_id"] is None


def test_upsert_rejects_list_without_writing(tmp_path: Path):
    store = _make_store(tmp_path)
    with pytest.raises(HTTPException) as exc:
        store.upsert_window([_sample_window()], ASSIGNABLE)
    assert exc.value.detail == "window must be an object"
    assert store.load_windows() == []
    assert not Path(store._file).exists()


def test_upsert_grandfathers_stored_owner(tmp_path: Path):
    store = _make_store(tmp_path)
    mock_config = _mock_closed_retention("7d")
    try:
        existing = _sample_window("w1")
        existing["owner_id"] = "U999"
        _seed_windows(store, [existing])
        ok, _before, saved = store.upsert_window(existing, ASSIGNABLE)
        assert ok is True
        assert saved[0]["owner_id"] == "U999"
    finally:
        mock_config.stop()
