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
