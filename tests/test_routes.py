from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes import create_router


def test_chains_config_uses_assignable_users_for_ui_chains():
    app = FastAPI()

    messenger = Mock()
    messenger.users = Mock()
    messenger.users.get_assignable_users.return_value = [
        {"user_id": "U1", "full_name": "User One", "config_name": "user.one"},
        {"user_id": "U2", "full_name": "User Two", "config_name": ""},
    ]
    messenger.user_groups = {"ops": Mock()}
    messenger.groups = {"team-a": Mock()}
    messenger.chains = {
        "primary": {"type": "ui"},
        "secondary": {"type": "direct"},
    }

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
        "ui_chains": ["primary"],
    }
    messenger.users.get_assignable_users.assert_called_once_with()


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
