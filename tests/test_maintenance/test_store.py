from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app.config.validation import IncidentTimeouts
from app.maintenance.models import MaintenanceWindow
from app.maintenance.store import MaintenanceStore


def _make_store(tmp_path: Path) -> MaintenanceStore:
    with patch("app.maintenance.store.get_environment_config") as mock_env:
        mock_env.return_value.data_path = str(tmp_path)
        return MaintenanceStore()


def _mock_closed_retention(closed: str = "7d"):
    timeouts = IncidentTimeouts(closed=closed)
    mock_config = patch("app.maintenance.store.get_config").start()
    mock_config.return_value.incident.timeouts = timeouts
    return mock_config


def _sample_window(window_id: str = "w1") -> dict:
    return {
        "id": window_id,
        "start": "2026-06-20T08:00:00+00:00",
        "end": "2026-06-20T12:00:00+00:00",
        "matchers": ['service="postgres"'],
        "comment": "planned work",
        "created_by": "alice",
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

        assert store.save_windows(windows) is True
        loaded = store.load_windows()
        assert len(loaded) == 2
        by_id = {w["id"]: w for w in loaded}
        assert by_id["w1"]["comment"] == "planned work"
        assert by_id["w1"]["created_by"] == "alice"
        assert by_id["w2"]["matchers"] == ['service="elastic"', 'env="prod"']
    finally:
        mock_config.stop()


def test_list_returns_maintenance_window_objects(tmp_path: Path):
    store = _make_store(tmp_path)
    mock_config = _mock_closed_retention("7d")
    try:
        store.save_windows([_sample_window()])
        windows = store.list()
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
