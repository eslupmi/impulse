from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app.config.validation import IncidentTimeouts
from app.im.chain.ui_chains_store import UIChainsStore


def _make_store(tmp_path: Path) -> UIChainsStore:
    with patch("app.im.chain.ui_chains_store.get_environment_config") as mock_get_environment_config:
        mock_get_environment_config.return_value.data_path = str(tmp_path)
        return UIChainsStore()


def _mock_closed_retention(closed: str = "7d"):
    timeouts = IncidentTimeouts(closed=closed)
    mock_config = patch("app.im.chain.ui_chains_store.get_config").start()
    mock_config.return_value.incident.timeouts = timeouts
    return mock_config


def _write_shifts_unfiltered(store: UIChainsStore, chain_name: str, shifts: list) -> None:
    store._write_shifts(chain_name, store.recalculate_priorities(shifts))


def test_ui_chains_dir_uses_environment_data_path(tmp_path: Path):
    with patch("app.im.chain.ui_chains_store.get_environment_config") as mock_get_environment_config, \
            patch("app.im.chain.ui_chains_store.os.path.exists", return_value=True):
        mock_get_environment_config.return_value.data_path = str(tmp_path)

        store = UIChainsStore()

    assert store.ui_chains_dir == str(tmp_path / "ui_chains")


def test_get_steps_for_now_prefers_priority_1(tmp_path: Path):
    with patch("app.im.chain.ui_chains_store.get_environment_config") as mock_get_environment_config, \
            patch("app.im.chain.ui_chains_store.os.path.exists", return_value=True):
        mock_get_environment_config.return_value.data_path = str(tmp_path)
        store = UIChainsStore()

    now = datetime(2026, 3, 29, 12, 0, tzinfo=timezone.utc)
    chains = [
        {
            "id": "low-priority",
            "start": "2026-03-29T11:00:00+00:00",
            "end": "2026-03-29T13:00:00+00:00",
            "priority": 2,
            "steps": [{"user": "user2"}],
        },
        {
            "id": "high-priority",
            "start": "2026-03-29T11:00:00+00:00",
            "end": "2026-03-29T13:00:00+00:00",
            "priority": 1,
            "steps": [{"user": "user1"}],
        },
    ]

    with patch.object(store, "load_shifts", return_value=chains):
        assert store.get_steps_for_now("test", now) == [{"user": "user1"}]


def test_recalculate_priorities_single_over_daily_repeat(tmp_path: Path):
    with patch("app.im.chain.ui_chains_store.get_environment_config") as mock_get_environment_config, \
            patch("app.im.chain.ui_chains_store.os.path.exists", return_value=True):
        mock_get_environment_config.return_value.data_path = str(tmp_path)
        store = UIChainsStore()

    chains = [
        {
            "id": "mnnf5iz2sv9io9s30yh",
            "start": "2026-04-07T13:00:00Z",
            "end": "2026-04-07T14:00:00Z",
            "repeat": "daily",
            "repeatEnd": None,
            "steps": [{"user_group": "both"}],
            "priority": 2,
        },
        {
            "id": "mnne7fqvs5q3r6l2ci",
            "start": "2026-04-09T12:30:00Z",
            "end": "2026-04-09T14:30:00Z",
            "repeat": None,
            "repeatEnd": None,
            "steps": [{"user": "u"}],
            "priority": 2,
        },
    ]
    out = store.recalculate_priorities(chains)
    by_id = {c["id"]: c["priority"] for c in out}
    assert by_id["mnne7fqvs5q3r6l2ci"] == 1
    assert by_id["mnnf5iz2sv9io9s30yh"] == 2


def test_prune_expired_shifts_removes_old_one_off_shift(tmp_path: Path):
    store = _make_store(tmp_path)
    mock_config = _mock_closed_retention("7d")
    now = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)

    try:
        old_shift = {
            "id": "old",
            "start": "2026-05-01T10:00:00Z",
            "end": "2026-05-01T12:00:00Z",
            "steps": [{"user": "alice"}],
        }
        recent_shift = {
            "id": "recent",
            "start": "2026-06-10T10:00:00Z",
            "end": "2026-06-10T12:00:00Z",
            "steps": [{"user": "bob"}],
        }
        _write_shifts_unfiltered(store, "primary", [old_shift, recent_shift])

        removed = store.prune_expired_shifts("primary", now)
        assert removed == 1

        remaining = store.load_shifts("primary")
        assert len(remaining) == 1
        assert remaining[0]["id"] == "recent"
    finally:
        mock_config.stop()


def test_prune_expired_shifts_keeps_repeating_shift_without_repeat_end(tmp_path: Path):
    store = _make_store(tmp_path)
    mock_config = _mock_closed_retention("7d")
    now = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)

    try:
        repeating_shift = {
            "id": "daily",
            "start": "2020-01-01T10:00:00Z",
            "end": "2020-01-01T12:00:00Z",
            "repeat": "daily",
            "repeatEnd": None,
            "steps": [{"user": "oncall"}],
        }
        store.save_shifts("primary", [repeating_shift])

        removed = store.prune_expired_shifts("primary", now)
        assert removed == 0
        assert len(store.load_shifts("primary")) == 1
    finally:
        mock_config.stop()


def test_prune_expired_shifts_removes_repeating_shift_with_past_repeat_end(tmp_path: Path):
    store = _make_store(tmp_path)
    mock_config = _mock_closed_retention("7d")
    now = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)

    try:
        ended_repeat = {
            "id": "ended",
            "start": "2026-05-01T10:00:00Z",
            "end": "2026-05-01T12:00:00Z",
            "repeat": "daily",
            "repeatEnd": "2026-05-05T12:00:00Z",
            "steps": [{"user": "alice"}],
        }
        _write_shifts_unfiltered(store, "primary", [ended_repeat])

        removed = store.prune_expired_shifts("primary", now)
        assert removed == 1
        assert store.load_shifts("primary") == []
    finally:
        mock_config.stop()


def test_save_shifts_filters_expired_shifts(tmp_path: Path):
    store = _make_store(tmp_path)
    mock_config = _mock_closed_retention("7d")
    fixed_now = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)

    try:
        old_shift = {
            "id": "old",
            "start": "2026-01-01T10:00:00Z",
            "end": "2026-01-01T12:00:00Z",
            "steps": [{"user": "alice"}],
        }
        recent_shift = {
            "id": "recent",
            "start": "2026-06-10T10:00:00Z",
            "end": "2026-06-10T12:00:00Z",
            "steps": [{"user": "bob"}],
        }

        def filter_at_fixed_now(shifts, now=None):
            return UIChainsStore.filter_retained_shifts(store, shifts, fixed_now)

        store.filter_retained_shifts = filter_at_fixed_now
        store.save_shifts("primary", [old_shift, recent_shift])

        remaining = store.load_shifts("primary")
        assert len(remaining) == 1
        assert remaining[0]["id"] == "recent"
    finally:
        mock_config.stop()


def test_prune_all_prunes_multiple_chain_files(tmp_path: Path):
    store = _make_store(tmp_path)
    mock_config = _mock_closed_retention("7d")
    now = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)

    try:
        old_shift = {
            "id": "old",
            "start": "2026-01-01T10:00:00Z",
            "end": "2026-01-01T12:00:00Z",
            "steps": [{"user": "alice"}],
        }
        _write_shifts_unfiltered(store, "primary", [old_shift])
        _write_shifts_unfiltered(store, "backup", [old_shift])

        removed = store.prune_all(now)
        assert removed == 2
        assert store.load_shifts("primary") == []
        assert store.load_shifts("backup") == []
    finally:
        mock_config.stop()
def test_ical_dt_to_iso_appends_z_for_naive(tmp_path: Path):
    from app.im.chain.ui_chains_store import _ical_dt_to_iso
    from datetime import datetime

    assert _ical_dt_to_iso(datetime(2026, 3, 15, 12, 0, 0)).endswith("Z")


def test_next_occurrence_start_monthly_and_yearly(tmp_path: Path):
    from app.im.chain.ui_chains_store import _next_occurrence_start
    from datetime import datetime, timezone

    base = datetime(2026, 1, 31, 10, 0, tzinfo=timezone.utc)
    current = datetime(2026, 1, 31, 10, 0, tzinfo=timezone.utc)
    monthly = _next_occurrence_start(base, current, "monthly")
    assert monthly.month == 2
    assert monthly.day == 28

    yearly_base = datetime(2024, 2, 29, 8, 0, tzinfo=timezone.utc)
    yearly_current = datetime(2024, 2, 29, 8, 0, tzinfo=timezone.utc)
    yearly = _next_occurrence_start(yearly_base, yearly_current, "yearly")
    assert yearly.year == 2025
    assert yearly.month == 2
    assert yearly.day == 28


def test_does_chain_overlap_range_repeating_daily(tmp_path: Path):
    with patch("app.im.chain.ui_chains_store.get_environment_config") as mock_get_environment_config, \
            patch("app.im.chain.ui_chains_store.os.path.exists", return_value=True):
        mock_get_environment_config.return_value.data_path = str(tmp_path)
        store = UIChainsStore()

    chain = {
        "id": "daily-shift",
        "start": "2026-06-01T09:00:00+00:00",
        "end": "2026-06-01T17:00:00+00:00",
        "repeat": "daily",
        "repeatEnd": "2026-06-05T17:00:00+00:00",
    }
    range_start = datetime(2026, 6, 3, 8, 0, tzinfo=timezone.utc)
    range_end = datetime(2026, 6, 3, 18, 0, tzinfo=timezone.utc)
    assert store._does_chain_overlap_range(chain, range_start, range_end) is True

    outside_range = datetime(2026, 6, 10, 8, 0, tzinfo=timezone.utc)
    outside_end = datetime(2026, 6, 10, 18, 0, tzinfo=timezone.utc)
    assert store._does_chain_overlap_range(chain, outside_range, outside_end) is False
