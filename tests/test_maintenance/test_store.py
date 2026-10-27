from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from icalendar import Calendar

from app.config.validation import IncidentTimeouts
from app.migrator import LEGACY_FILENAME, MaintenanceMigrator
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


def _window_files(store: MaintenanceStore) -> list[Path]:
    return sorted(path for path in Path(store._dir).glob("*.ics") if path.name != LEGACY_FILENAME)


def _seed_windows(store: MaintenanceStore, windows: list[dict]) -> None:
    for window in windows:
        assert store._write_window_unlocked(window) is True


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


def test_upsert_writes_uid_file(tmp_path: Path):
    store = _make_store(tmp_path)
    mock_config = _mock_closed_retention("7d")
    try:
        assert store.upsert_window(_sample_window(), ASSIGNABLE)[0] is True
        files = _window_files(store)
        assert len(files) == 1
        assert files[0].name == "w1.ics"
        assert store.upsert_window(_sample_window(), ASSIGNABLE)[0] is True
        assert _window_files(store) == files
        assert not (Path(store._dir) / LEGACY_FILENAME).exists()
    finally:
        mock_config.stop()


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
        _seed_windows(store, [old, recent])

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
    cal_path = Path(store._dir) / LEGACY_FILENAME
    with open(cal_path, "wb") as f:
        f.write(
            b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n"
            b"BEGIN:VEVENT\r\nUID:no-matchers\r\n"
            b"DTSTART:20260620T080000Z\r\nDTEND:20260620T120000Z\r\n"
            b"SUMMARY:test\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
        )
    store.migrate()
    assert store.load_windows() == []
    assert not cal_path.exists()


def test_load_window_without_owner_id(tmp_path: Path):
    store = _make_store(tmp_path)
    with open(Path(store._dir) / LEGACY_FILENAME, "wb") as f:
        f.write(
            b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n"
            b"BEGIN:VEVENT\r\nUID:legacy\r\n"
            b"DTSTART:20260620T080000Z\r\nDTEND:20260620T120000Z\r\n"
            b"SUMMARY:test\r\n"
            b"X-MATCHER:alertname=\"A\"\r\n"
            b"END:VEVENT\r\nEND:VCALENDAR\r\n"
        )
    store.migrate()
    loaded = store.load_windows()
    assert len(loaded) == 1
    assert loaded[0]["id"] == "legacy"
    assert loaded[0]["owner_id"] is None


def test_legacy_windows_ics_splits_on_load(tmp_path: Path):
    store = _make_store(tmp_path)
    legacy = Path(store._dir) / LEGACY_FILENAME
    legacy.write_bytes(
        b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n"
        b"BEGIN:VEVENT\r\nUID:a\r\n"
        b"DTSTART:20260620T080000Z\r\nDTEND:20260620T120000Z\r\n"
        b"SUMMARY:a\r\nX-MATCHER:alertname=\"A\"\r\n"
        b"END:VEVENT\r\n"
        b"BEGIN:VEVENT\r\nUID:b\r\n"
        b"DTSTART:20260621T090000Z\r\nDTEND:20260621T130000Z\r\n"
        b"SUMMARY:b\r\nX-MATCHER:alertname=\"B\"\r\n"
        b"END:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    store.migrate()
    loaded = store.load_windows()
    assert {window["id"] for window in loaded} == {"a", "b"}
    assert not legacy.exists()
    files = _window_files(store)
    assert len(files) == 2
    assert {path.name for path in files} == {"a.ics", "b.ics"}
    for path in files:
        event = Calendar.from_ical(path.read_bytes()).walk("VEVENT")[0]
        assert event.get("dtstamp") is None
    store.migrate()
    assert len(_window_files(store)) == 2
    version = Calendar.from_ical(files[0].read_bytes().decode()).get("x-impulse-version")
    assert str(version) == MaintenanceMigrator.ACTUAL_VERSION
    before = {path.name: path.read_bytes() for path in files}
    MaintenanceMigrator().downgrade(store, MaintenanceMigrator.LEGACY_VERSION)
    assert all(event.get("dtstamp") is None for event in Calendar.from_ical(legacy.read_bytes()).walk("VEVENT"))
    store.migrate()
    assert {path.name: path.read_bytes() for path in _window_files(store)} == before


@pytest.mark.parametrize('version', ['v3.6.0', 'v3.9.0'])
def test_upgrade_rejects_unknown_schema_without_changing_files(tmp_path: Path, version):
    store = _make_store(tmp_path)
    assert store._write_legacy_file([_sample_window()])
    legacy = Path(store._dir) / LEGACY_FILENAME
    calendar = Calendar.from_ical(legacy.read_bytes())
    calendar['x-impulse-version'] = version
    legacy.write_bytes(calendar.to_ical())
    before = legacy.read_bytes()

    with pytest.raises(ValueError, match='No migration path'):
        store.migrate()

    assert legacy.read_bytes() == before
    assert _window_files(store) == []


@pytest.mark.parametrize(
    'current, target',
    [
        ('v3.8.0', 'v3.8.0'),
        ('v3.7.0', 'v3.7.0'),
        ('v3.9.0', 'v3.7.0'),
        ('v3.8.0', 'v3.6.0'),
        ('v3.8.0', 'v3.9.0'),
    ],
)
def test_downgrade_without_supported_transition_keeps_files(tmp_path: Path, current, target):
    store = _make_store(tmp_path)
    _seed_windows(store, [_sample_window()])
    path = _window_files(store)[0]
    calendar = Calendar.from_ical(path.read_bytes())
    calendar['x-impulse-version'] = current
    path.write_bytes(calendar.to_ical())
    before = path.read_bytes()

    MaintenanceMigrator().downgrade(store, target)

    assert _window_files(store) == [path]
    assert path.read_bytes() == before
    assert not (Path(store._dir) / LEGACY_FILENAME).exists()


def test_downgrade_merges_windows_ics(tmp_path: Path):
    store = _make_store(tmp_path)
    legacy = Path(store._dir) / LEGACY_FILENAME
    legacy.write_bytes(
        b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//test//EN\r\n"
        b"BEGIN:VEVENT\r\nUID:a\r\n"
        b"DTSTART:20260620T080000Z\r\nDTEND:20260620T120000Z\r\n"
        b"DTSTAMP:20260601T101112Z\r\n"
        b"SUMMARY:a\r\nX-MATCHER:alertname=\"A\"\r\n"
        b"END:VEVENT\r\n"
        b"BEGIN:VEVENT\r\nUID:b\r\n"
        b"DTSTART:20260621T090000Z\r\nDTEND:20260621T130000Z\r\n"
        b"DTSTAMP:20260602T131415Z\r\n"
        b"SUMMARY:b\r\nX-MATCHER:alertname=\"B\"\r\n"
        b"END:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    store.migrate()
    original = {path.name: path.read_bytes() for path in _window_files(store)}
    assert set(original) == {"a.ics", "b.ics"}
    stamps = {"a": b"20260601T101112Z", "b": b"20260602T131415Z"}
    for _ in range(2):
        MaintenanceMigrator().downgrade(store, MaintenanceMigrator.LEGACY_VERSION)
        assert legacy.exists()
        assert _window_files(store) == []
        restored = Calendar.from_ical(legacy.read_bytes())
        assert str(restored.get("x-impulse-version")) == MaintenanceMigrator.LEGACY_VERSION
        events = restored.walk("VEVENT")
        assert {str(event["uid"]): event["dtstamp"].to_ical() for event in events} == stamps
        MaintenanceMigrator().downgrade(store, MaintenanceMigrator.LEGACY_VERSION)
        assert legacy.exists()
        store.migrate()
        assert not legacy.exists()
        assert {path.name: path.read_bytes() for path in _window_files(store)} == original
        assert all("_dtstamp" not in window for window in store.load_windows())


def test_migrate_renames_timestamp_file_without_rewriting(tmp_path: Path):
    store = _make_store(tmp_path)
    _seed_windows(store, [_sample_window()])
    timestamp_path = Path(store._dir) / "2026-10-20-20-44-00-000000.ics"
    _window_files(store)[0].rename(timestamp_path)
    before = timestamp_path.read_bytes()

    store.migrate()

    uid_path = Path(store._dir) / "w1.ics"
    assert _window_files(store) == [uid_path]
    assert uid_path.read_bytes() == before
    assert store.load_windows()[0]["id"] == "w1"
    assert store.delete_window("w1")[0] is True
    assert _window_files(store) == []


def test_uid_filenames_escape_paths_and_reserved_name(tmp_path: Path):
    store = _make_store(tmp_path)
    names = {
        "a/b": "a%2Fb.ics",
        "a%2Fb": "a%252Fb.ics",
        "a\\b": "a%5Cb.ics",
        "../outside": "..%2Foutside.ics",
        "/absolute": "%2Fabsolute.ics",
        "windows": "%77indows.ics",
        "Windows": "%57indows.ics",
        "%77indows": "%2577indows.ics",
    }
    _seed_windows(store, [_sample_window(uid) for uid in names])
    assert {path.name for path in _window_files(store)} == set(names.values())
    assert {window["id"] for window in store.load_windows()} == set(names)
    assert not (Path(store._dir) / LEGACY_FILENAME).exists()


def test_migration_keeps_sources_when_uid_filename_is_occupied(tmp_path: Path):
    store = _make_store(tmp_path)
    assert store._write_legacy_file([_sample_window()])
    legacy = Path(store._dir) / LEGACY_FILENAME
    before = legacy.read_bytes()
    occupied = Path(store._dir) / "w1.ics"
    occupied.write_bytes(b"unreadable existing record")

    store.migrate()

    assert legacy.read_bytes() == before
    assert occupied.read_bytes() == b"unreadable existing record"


def test_rename_keeps_sources_when_uid_filename_is_occupied(tmp_path: Path):
    store = _make_store(tmp_path)
    _seed_windows(store, [_sample_window()])
    timestamp_path = Path(store._dir) / "2026-10-20-20-44-00-000000.ics"
    _window_files(store)[0].rename(timestamp_path)
    before = timestamp_path.read_bytes()
    occupied = Path(store._dir) / "w1.ics"
    occupied.write_bytes(b"unreadable existing record")

    with pytest.raises(FileExistsError):
        store.migrate()

    assert timestamp_path.read_bytes() == before
    assert occupied.read_bytes() == b"unreadable existing record"


def test_downgrade_keeps_unreadable_legacy_calendar(tmp_path: Path):
    store = _make_store(tmp_path)
    _seed_windows(store, [_sample_window()])
    before = {path.name: path.read_bytes() for path in _window_files(store)}
    legacy = Path(store._dir) / LEGACY_FILENAME
    legacy.write_bytes(b"unreadable legacy calendar")

    MaintenanceMigrator().downgrade(store, MaintenanceMigrator.LEGACY_VERSION)

    assert {path.name: path.read_bytes() for path in _window_files(store)} == before
    assert legacy.read_bytes() == b"unreadable legacy calendar"


def test_upsert_window_keeps_ownerless_sibling(tmp_path: Path):
    store = _make_store(tmp_path)
    mock_config = _mock_closed_retention("7d")
    try:
        legacy = _sample_window("legacy")
        legacy["owner_id"] = None
        _seed_windows(store, [legacy])
        before = {path.name: path.read_bytes() for path in _window_files(store)}
        assert len(before) == 1
        ok, _existing, _saved = store.upsert_window(_sample_window("new"), ASSIGNABLE)
        assert ok is True
        sibling_name = next(iter(before))
        assert (Path(store._dir) / sibling_name).read_bytes() == before[sibling_name]
        by_id = {w["id"]: w for w in store.load_windows()}
        assert by_id["legacy"]["owner_id"] is None
        assert by_id["new"]["owner_id"] == "U123"
        new_files = [path for path in _window_files(store) if path.name != sibling_name]
        assert len(new_files) == 1
        assert b"X-OWNER-ID:U123" in new_files[0].read_bytes()
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
        _seed_windows(store, [recent, old])
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
    before = {path.name: path.read_bytes() for path in _window_files(store)}
    with pytest.raises(HTTPException) as exc:
        store.upsert_window(legacy, ASSIGNABLE)
    assert exc.value.detail == "owner_id is required"
    assert {path.name: path.read_bytes() for path in _window_files(store)} == before
    loaded = store.load_windows()
    assert loaded[0]["id"] == "legacy"
    assert loaded[0]["owner_id"] is None


def test_upsert_rejects_list_without_writing(tmp_path: Path):
    store = _make_store(tmp_path)
    payload = [_sample_window()]
    with pytest.raises(HTTPException) as exc:
        store.upsert_window(payload, ASSIGNABLE)
    assert exc.value.detail == "window must be an object"
    assert store.load_windows() == []
    assert _window_files(store) == []


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
