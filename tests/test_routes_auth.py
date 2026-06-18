from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.maintenance.models import MaintenanceWindow
from app.routes import create_router


SESSION_COOKIE = "impulse_auth_session"
AUTHENTICATED_USER = {"id": "U1", "username": "alice", "full_name": "Alice"}


def _mock_messenger(**overrides):
    messenger = Mock()
    messenger.type = Mock()
    messenger.type.value = "slack"
    for key, value in overrides.items():
        setattr(messenger, key, value)
    return messenger


def _mock_config(messenger):
    config = Mock()
    config.app = Mock()
    config.app.webhooks = {}
    config.app.general = Mock()
    config.app.general.week_start = "Mon"
    config.app.general.timezone = "UTC"
    config.messenger = messenger
    return config


def _mock_auth_manager(*, authenticated: bool):
    manager = Mock()
    manager.session_cookie_name = SESSION_COOKIE
    if authenticated:
        manager.get_current_user = Mock(return_value={
            "authenticated": True,
            "user": AUTHENTICATED_USER,
        })
    else:
        manager.get_current_user = Mock(return_value={"authenticated": False})
    return manager


MATCHER = 'alertname = "Test"'


def _maintenance_payload():
    start = datetime.now(timezone.utc).replace(microsecond=0)
    return {
        "start": start.isoformat(),
        "durationMs": 3_600_000,
        "matchers": [MATCHER],
        "comment": "planned work",
    }


@pytest.fixture
def messenger():
    return _mock_messenger(
        users=Mock(),
        user_groups={},
        groups={},
        chains={"primary": {"type": "ui"}},
    )


@pytest.fixture
def config(messenger):
    messenger.users.get_assignable_users.return_value = [
        {"user_id": "U1", "full_name": "Alice", "config_name": "alice"},
    ]
    return _mock_config(messenger)


def _build_app(config, messenger, auth_manager):
    app = FastAPI()
    app.state.messenger = messenger
    app.state.incidents = Mock()
    app.state.is_standby = False
    app.state.maintenance_manager = Mock()
    app.state.maintenance_manager.reconcile_after_window_removed = AsyncMock()
    app.include_router(create_router("", auth_manager=auth_manager))
    return app


@pytest.fixture
def unauthenticated_client(config, messenger):
    app = _build_app(config, messenger, _mock_auth_manager(authenticated=False))
    with patch("app.routes.get_config", return_value=config):
        yield TestClient(app)


@pytest.fixture
def authenticated_client(config, messenger):
    app = _build_app(config, messenger, _mock_auth_manager(authenticated=True))
    with patch("app.routes.get_config", return_value=config):
        yield TestClient(app, cookies={SESSION_COOKIE: "valid-session"})


class TestPrivilegedRoutesRequireAuth:
    def test_chains_config_returns_401_when_unauthenticated(self, unauthenticated_client):
        response = unauthenticated_client.get("/chains_config")
        assert response.status_code == 401

    def test_chains_config_returns_200_when_authenticated(self, authenticated_client):
        response = authenticated_client.get("/chains_config")
        assert response.status_code == 200
        assert response.json()["ui_chains"] == ["primary"]

    def test_get_maintenance_returns_401_when_unauthenticated(self, unauthenticated_client):
        with patch("app.routes.get_maintenance_store") as mock_store:
            mock_store.return_value.list.return_value = []
            response = unauthenticated_client.get("/maintenance")
        assert response.status_code == 401

    def test_get_maintenance_returns_200_when_authenticated(self, authenticated_client):
        window = MaintenanceWindow(
            starts_at=datetime.now(timezone.utc),
            ends_at=datetime.now(timezone.utc) + timedelta(hours=1),
            matchers=[MATCHER],
            comment="work",
        )
        with patch("app.routes.get_maintenance_store") as mock_store:
            mock_store.return_value.list.return_value = [window]
            response = authenticated_client.get("/maintenance")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_post_maintenance_returns_401_when_unauthenticated(self, unauthenticated_client):
        response = unauthenticated_client.post("/maintenance", json=_maintenance_payload())
        assert response.status_code == 401

    def test_post_maintenance_returns_200_when_authenticated(self, authenticated_client):
        store = Mock()
        with patch("app.routes.get_maintenance_store", return_value=store), \
                patch("app.routes.reconcile_maintenance", new_callable=AsyncMock):
            response = authenticated_client.post("/maintenance", json=_maintenance_payload())
        assert response.status_code == 200
        store.upsert.assert_called_once()
        saved_window = store.upsert.call_args[0][0]
        assert saved_window.created_by == "alice"

    def test_put_maintenance_returns_401_when_unauthenticated(self, unauthenticated_client):
        response = unauthenticated_client.put("/maintenance/w1", json=_maintenance_payload())
        assert response.status_code == 401

    def test_put_maintenance_returns_200_when_authenticated(self, authenticated_client):
        store = Mock()
        store.get.return_value = Mock()
        with patch("app.routes.get_maintenance_store", return_value=store), \
                patch("app.routes.reconcile_maintenance", new_callable=AsyncMock):
            response = authenticated_client.put("/maintenance/w1", json=_maintenance_payload())
        assert response.status_code == 200
        store.upsert.assert_called_once()

    def test_delete_maintenance_returns_401_when_unauthenticated(self, unauthenticated_client):
        response = unauthenticated_client.delete("/maintenance/w1")
        assert response.status_code == 401

    def test_delete_maintenance_returns_200_when_authenticated(self, authenticated_client):
        window = MaintenanceWindow(
            id="w1",
            starts_at=datetime.now(timezone.utc),
            ends_at=datetime.now(timezone.utc) + timedelta(hours=1),
            matchers=[MATCHER],
            comment="work",
        )
        store = Mock()
        store.get.return_value = window
        with patch("app.routes.get_maintenance_store", return_value=store):
            response = authenticated_client.delete("/maintenance/w1")
        assert response.status_code == 200
        store.delete.assert_called_once_with("w1")


class TestUiChainsWebsocketAuth:
    def test_save_ui_chains_rejected_when_unauthenticated(self, config, messenger):
        auth_manager = _mock_auth_manager(authenticated=False)
        app = _build_app(config, messenger, auth_manager)
        with patch("app.routes.get_config", return_value=config), \
                patch("app.routes.ui_chains_store") as mock_store:
            with TestClient(app) as client:
                with client.websocket_connect("/ws") as ws:
                    ws.send_json({
                        "event": "save_ui_chains",
                        "chain_name": "primary",
                        "data": [],
                    })
                    message = ws.receive_json()
            mock_store.save_shifts.assert_not_called()
        assert message == {
            "event": "ui_chains_saved",
            "success": False,
            "detail": "Authentication required",
        }

    def test_request_ui_chains_rejected_when_unauthenticated(self, config, messenger):
        auth_manager = _mock_auth_manager(authenticated=False)
        app = _build_app(config, messenger, auth_manager)
        with patch("app.routes.get_config", return_value=config), \
                patch("app.routes.ui_chains_store") as mock_store:
            with TestClient(app) as client:
                with client.websocket_connect("/ws") as ws:
                    ws.send_json({
                        "event": "request_ui_chains",
                        "chain_name": "primary",
                    })
                    message = ws.receive_json()
            mock_store.load_shifts.assert_not_called()
        assert message == {
            "event": "ui_chains_error",
            "detail": "Authentication required",
        }

    def test_save_ui_chains_allowed_when_authenticated(self, config, messenger):
        auth_manager = _mock_auth_manager(authenticated=True)
        app = _build_app(config, messenger, auth_manager)
        with patch("app.routes.get_config", return_value=config), \
                patch("app.routes.ui_chains_store") as mock_store:
            mock_store.save_shifts.return_value = True
            with TestClient(app, cookies={SESSION_COOKIE: "valid-session"}) as client:
                with client.websocket_connect("/ws") as ws:
                    ws.send_json({
                        "event": "save_ui_chains",
                        "chain_name": "primary",
                        "data": [{"id": "shift-1"}],
                    })
                    message = ws.receive_json()
            mock_store.save_shifts.assert_called_once_with("primary", [{"id": "shift-1"}])
        assert message == {"event": "ui_chains_saved", "success": True}
