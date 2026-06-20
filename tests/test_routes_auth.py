from unittest.mock import AsyncMock, Mock, patch

import pytest
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient

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


def _maintenance_ws_payload():
    start = datetime.now(timezone.utc).replace(microsecond=0)
    end = start + timedelta(hours=1)
    return [{
        "id": "w1",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "matchers": [MATCHER],
        "comment": "planned work",
    }]


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
    app.state.maintenance_manager.reconcile_all = AsyncMock()
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


class TestMaintenanceWebsocketAuth:
    def test_save_maintenance_rejected_when_unauthenticated(self, config, messenger):
        auth_manager = _mock_auth_manager(authenticated=False)
        app = _build_app(config, messenger, auth_manager)
        with patch("app.routes.get_config", return_value=config), \
                patch("app.routes.get_maintenance_store") as mock_store:
            with TestClient(app) as client:
                with client.websocket_connect("/ws") as ws:
                    ws.send_json({
                        "event": "save_maintenance",
                        "data": _maintenance_ws_payload(),
                    })
                    message = ws.receive_json()
            mock_store.return_value.save_windows.assert_not_called()
        assert message == {
            "event": "maintenance_saved",
            "success": False,
            "detail": "Authentication required",
        }

    def test_request_maintenance_rejected_when_unauthenticated(self, config, messenger):
        auth_manager = _mock_auth_manager(authenticated=False)
        app = _build_app(config, messenger, auth_manager)
        with patch("app.routes.get_config", return_value=config), \
                patch("app.routes.get_maintenance_store") as mock_store:
            with TestClient(app) as client:
                with client.websocket_connect("/ws") as ws:
                    ws.send_json({"event": "request_maintenance"})
                    message = ws.receive_json()
            mock_store.return_value.load_windows.assert_not_called()
        assert message == {
            "event": "maintenance_error",
            "detail": "Authentication required",
        }

    def test_save_maintenance_allowed_when_authenticated(self, config, messenger):
        auth_manager = _mock_auth_manager(authenticated=True)
        app = _build_app(config, messenger, auth_manager)
        with patch("app.routes.get_config", return_value=config), \
                patch("app.routes.get_maintenance_store") as mock_store, \
                patch("app.routes.merge_and_validate_save") as mock_validate:
            mock_store.return_value.load_windows.return_value = []
            mock_store.return_value.save_windows.return_value = True
            mock_validate.return_value = _maintenance_ws_payload()
            with TestClient(app, cookies={SESSION_COOKIE: "valid-session"}) as client:
                with client.websocket_connect("/ws") as ws:
                    ws.send_json({
                        "event": "save_maintenance",
                        "data": _maintenance_ws_payload(),
                    })
                    message = ws.receive_json()
            mock_store.return_value.save_windows.assert_called_once()
            app.state.maintenance_manager.reconcile_after_window_removed.assert_not_called()
            app.state.maintenance_manager.reconcile_all.assert_awaited_once()
        assert message == {"event": "maintenance_saved", "success": True}

    def test_save_maintenance_reconciles_removed_windows(self, config, messenger):
        auth_manager = _mock_auth_manager(authenticated=True)
        app = _build_app(config, messenger, auth_manager)
        existing = _maintenance_ws_payload()
        with patch("app.routes.get_config", return_value=config), \
                patch("app.routes.get_maintenance_store") as mock_store, \
                patch("app.routes.merge_and_validate_save") as mock_validate:
            mock_store.return_value.load_windows.return_value = existing
            mock_store.return_value.save_windows.return_value = True
            mock_validate.return_value = []
            with TestClient(app, cookies={SESSION_COOKIE: "valid-session"}) as client:
                with client.websocket_connect("/ws") as ws:
                    ws.send_json({
                        "event": "save_maintenance",
                        "data": [],
                    })
                    message = ws.receive_json()
            removed_window = app.state.maintenance_manager.reconcile_after_window_removed.await_args.args[0]
            assert removed_window.matchers == existing[0]["matchers"]
        assert message == {"event": "maintenance_saved", "success": True}

    def test_request_maintenance_allowed_when_authenticated(self, config, messenger):
        auth_manager = _mock_auth_manager(authenticated=True)
        app = _build_app(config, messenger, auth_manager)
        payload = _maintenance_ws_payload()
        with patch("app.routes.get_config", return_value=config), \
                patch("app.routes.get_maintenance_store") as mock_store:
            mock_store.return_value.load_windows.return_value = payload
            with TestClient(app, cookies={SESSION_COOKIE: "valid-session"}) as client:
                with client.websocket_connect("/ws") as ws:
                    ws.send_json({"event": "request_maintenance"})
                    message = ws.receive_json()
            mock_store.return_value.prune_expired_windows.assert_called_once()
            mock_store.return_value.load_windows.assert_called_once()
        assert message == {"event": "maintenance_data", "data": payload}


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
