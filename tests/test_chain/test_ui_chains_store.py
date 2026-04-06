from datetime import datetime, timezone
from unittest.mock import patch

from app.im.chain.ui_chains_store import UIChainsStore


def test_ui_chains_dir_uses_environment_data_path():
    with patch("app.im.chain.ui_chains_store.get_environment_config") as mock_get_environment_config, \
            patch("app.im.chain.ui_chains_store.os.path.exists", return_value=True):
        mock_get_environment_config.return_value.data_path = "/tmp/impulse-data"

        store = UIChainsStore()

    assert store.ui_chains_dir == "/tmp/impulse-data/ui_chains"


def test_get_steps_for_now_prefers_priority_1():
    with patch("app.im.chain.ui_chains_store.get_environment_config") as mock_get_environment_config, \
            patch("app.im.chain.ui_chains_store.os.path.exists", return_value=True):
        mock_get_environment_config.return_value.data_path = "/tmp/impulse-data"
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

    with patch.object(store, "load_chains", return_value=chains):
        assert store.get_steps_for_now("test", now) == [{"user": "user1"}]


def test_recalculate_priorities_single_over_daily_repeat():
    with patch("app.im.chain.ui_chains_store.get_environment_config") as mock_get_environment_config, \
            patch("app.im.chain.ui_chains_store.os.path.exists", return_value=True):
        mock_get_environment_config.return_value.data_path = "/tmp/impulse-data"
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
