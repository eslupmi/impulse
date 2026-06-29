from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes import create_router


def _mock_messenger(**overrides):
    messenger = Mock()
    messenger.type = Mock()
    messenger.type.value = "slack"
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
