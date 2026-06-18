from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app.im.chain.ui_chains_store import UIChainsStore


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
