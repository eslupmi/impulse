from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config.config import UnifiedConfig, get_config
from app.config.loader import load_and_validate_config
from app.routes import create_router


@pytest.mark.parametrize("http_prefix", ["", "/impulse"])
def test_ui_can_be_enabled_and_disabled_by_reload(tmp_path, monkeypatch, http_prefix):
    from app import lifespan, routes
    from app.config import config as config_module

    config_path = tmp_path / "impulse.yml"
    base_config = "messenger:\n  type: none\n"
    ui_config = "ui:\n  columns:\n    - name: status\n      header: Status\n      value: incident.status\n"
    config_path.write_text(base_config)

    def load_config(exit_on_error=True):
        return UnifiedConfig(load_and_validate_config(str(config_path))[0])

    monkeypatch.setattr(config_module, "_config", load_config())
    monkeypatch.setattr(config_module, "get_config", get_config)
    monkeypatch.setattr(config_module, "load_unified_config", load_config)
    monkeypatch.setattr(routes, "get_config", get_config)
    cleanup = AsyncMock()
    create = AsyncMock()
    monkeypatch.setattr(lifespan, "_cleanup_application_objects", cleanup)
    monkeypatch.setattr(lifespan, "create_main_objects", create)

    app = FastAPI()
    app.state.queue = AsyncMock()
    app.include_router(create_router(http_prefix, fastapi_app=app))
    route_count = len(app.routes)
    with TestClient(app) as client:
        assert client.get(f"{http_prefix}/").status_code == 405
        assert client.get(f"{http_prefix}/static/index.html").status_code == 404

        config_path.write_text(base_config + ui_config)
        assert client.post(f"{http_prefix}/-/reload").status_code == 200
        cleanup.assert_awaited_once_with(app, reload=True)
        create.assert_awaited_once_with(app, reload=True)
        assert client.get(f"{http_prefix}/static/css/style.css").status_code == 200
        response = client.get(f"{http_prefix}/")
        assert response.status_code == 200
        assert '<title>IMPulse</title>' in response.text
        assert f'href="{http_prefix}/static/css/style.css"' in response.text
        columns = client.get(f"{http_prefix}/ui_config").json()["table_config"]
        assert any(column["field"] == "status" for column in columns)
        assert client.post(f"{http_prefix}/", json={"status": "firing"}).status_code == 200
        app.state.queue.put_first.assert_awaited_once()

        config_path.write_text(base_config)
        assert client.post(f"{http_prefix}/-/reload").status_code == 200
        assert client.get(f"{http_prefix}/").status_code == 405
        assert client.get(f"{http_prefix}/static/index.html").status_code == 404

        config_path.write_text(base_config + ui_config)
        assert client.post(f"{http_prefix}/-/reload").status_code == 200
        assert client.get(f"{http_prefix}/").status_code == 200
        assert len(app.routes) == route_count


def _mock_messenger(**overrides):
    messenger = Mock()
    messenger.type = "slack"
    for key, value in overrides.items():
        setattr(messenger, key, value)
    return messenger


def test_chains_config_uses_assignable_users_for_ui_chains():
    app = FastAPI()

    messenger = _mock_messenger(
        users=Mock(),
        user_groups={"ops": Mock()},
        groups={"team-a": Mock()},
        chains={
            "primary": {"type": "ui"},
            "secondary": {"type": "direct"},
        },
    )
    messenger.users.get_assignable_users.return_value = [
        {"user_id": "U1", "full_name": "User One", "config_name": "user.one"},
        {"user_id": "U2", "full_name": "User Two", "config_name": ""},
    ]

    config = Mock()
    config.app = Mock()
    config.app.webhooks = {"notify": Mock()}
    config.app.general = Mock()
    config.app.general.week_start = "Sun"
    config.app.general.timezone = "Europe/Berlin"
    config.messenger = messenger

    app.state.messenger = messenger
    app.include_router(create_router("", fastapi_app=app))

    client = TestClient(app)

    from app import routes as routes_module
    original_get_config = routes_module.get_config
    routes_module.get_config = lambda: config
    try:
        response = client.get("/chains_config")
    finally:
        routes_module.get_config = original_get_config

    assert response.status_code == 200
    assert response.json() == {
        "users": ["user.one"],
        "user_groups": ["ops"],
        "groups": ["team-a"],
        "chains": ["primary", "secondary"],
        "webhooks": ["notify"],
        "week_start": "Sun",
        "timezone": "Europe/Berlin",
        "messenger_type": "slack",
        "user_timezone": None,
        "ui_chains": ["primary"],
    }
    messenger.users.get_assignable_users.assert_called_once_with()


def test_chains_config_uses_runtime_messenger_not_raw_config():
    app = FastAPI()

    runtime_messenger = _mock_messenger(
        users=Mock(),
        user_groups={"ops": Mock()},
        groups={"team-a": Mock()},
        chains={
            "primary": {"type": "ui"},
        },
    )
    runtime_messenger.users.get_assignable_users.return_value = [
        {"user_id": "U1", "full_name": "User One", "config_name": "user.one"},
    ]

    raw_config_messenger = Mock()
    raw_config_messenger.users = {}
    raw_config_messenger.user_groups = {"ops": Mock()}
    raw_config_messenger.groups = {"team-a": Mock()}
    raw_config_messenger.chains = {
        "primary": {"type": "ui"},
    }

    config = Mock()
    config.app = Mock()
    config.app.webhooks = {"notify": Mock()}
    config.app.general = Mock()
    config.app.general.week_start = "Sun"
    config.app.general.timezone = "Europe/Berlin"
    config.messenger = raw_config_messenger

    app.state.messenger = runtime_messenger
    app.include_router(create_router("", fastapi_app=app))

    client = TestClient(app)

    from app import routes as routes_module
    original_get_config = routes_module.get_config
    routes_module.get_config = lambda: config
    try:
        response = client.get("/chains_config")
    finally:
        routes_module.get_config = original_get_config

    assert response.status_code == 200
    assert response.json()["users"] == ["user.one"]
    runtime_messenger.users.get_assignable_users.assert_called_once_with()


def test_chains_config_keeps_ui_chains_from_raw_config_when_runtime_chains_exclude_them():
    app = FastAPI()

    runtime_messenger = _mock_messenger(
        users=Mock(),
        user_groups={},
        groups={},
        chains={
            "primary": Mock(),
        },
    )
    runtime_messenger.users.get_assignable_users.return_value = []

    raw_config_messenger = Mock()
    raw_config_messenger.chains = {
        "primary": [],
        "ui-duty": {"type": "ui"},
        "ui-backup": {"type": "ui"},
    }

    config = Mock()
    config.app = Mock()
    config.app.webhooks = {}
    config.app.general = Mock()
    config.app.general.week_start = "Mon"
    config.app.general.timezone = "UTC"
    config.messenger = raw_config_messenger

    app.state.messenger = runtime_messenger
    app.include_router(create_router("", fastapi_app=app))

    client = TestClient(app)

    from app import routes as routes_module
    original_get_config = routes_module.get_config
    routes_module.get_config = lambda: config
    try:
        response = client.get("/chains_config")
    finally:
        routes_module.get_config = original_get_config

    assert response.status_code == 200
    assert response.json()["chains"] == ["primary"]
    assert response.json()["ui_chains"] == ["ui-duty", "ui-backup"]


def test_assignment_users_uses_assignable_users():
    app = FastAPI()

    messenger = Mock()
    messenger.users = Mock()
    messenger.users.get_assignable_users.return_value = [
        {"user_id": "U1", "full_name": "User One", "config_name": "user.one"},
    ]
    app.state.messenger = messenger
    app.include_router(create_router("", fastapi_app=app))

    client = TestClient(app)
    response = client.get("/assignment_users")

    assert response.status_code == 200
    assert response.json() == [
        {"user_id": "U1", "full_name": "User One", "config_name": "user.one"},
    ]
    messenger.users.get_assignable_users.assert_called_once_with()
