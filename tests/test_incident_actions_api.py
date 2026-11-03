from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.im.application import Application
from app.im.users import ProfileUser, UserManager
from app.incident.freeze import FreezeSource
from app.middleware import StandbyMiddleware
from app.queue.constants import QueueItemType
from app.routes import create_router
from impulse_messenger_api import ProviderDescriptor


@pytest.fixture
def actions(sample_incident):
    sample_incident.uniq_id = "inc-1"
    sample_incident.dump = Mock()
    messenger = Application.__new__(Application)
    messenger.provider = SimpleNamespace(descriptor=ProviderDescriptor("test"))
    messenger.users = UserManager()
    messenger.users.add_user(
        "U1", ProfileUser("alice", id_="U1", exists=True, username="alice"), "alice"
    )
    messenger._async_tasks = set()
    messenger.update_incident_message = AsyncMock()
    messenger.post_assignment_notification = AsyncMock()
    messenger.post_unassignment_notification = AsyncMock()
    messenger.post_freeze_notification = AsyncMock()
    messenger.task_management_integration = Mock(
        handle_button_press=AsyncMock(return_value={"task_link": "https://task/1"})
    )
    queue = Mock(
        delete_by_id=AsyncMock(),
        put=AsyncMock(),
        delete_by_id_and_type=AsyncMock(),
        put_first=AsyncMock(),
        recreate=AsyncMock(),
    )
    app = FastAPI()
    app.state.incidents = Mock(
        get_by_uniq_id=Mock(
            side_effect=lambda uid: sample_incident if uid == "inc-1" else None
        )
    )
    app.state.messenger = messenger
    app.state.queue = queue
    app.include_router(create_router("/impulse"))
    return SimpleNamespace(
        client=TestClient(app),
        app=app,
        incident=sample_incident,
        messenger=messenger,
        queue=queue,
    )


@pytest.mark.parametrize(
    "deadline", ["2099-08-02T21:00:00+03:00", "2099-08-02T18:00:00Z"]
)
def test_freeze_until_schedules_manual_unfreeze(actions, deadline):
    response = actions.client.post(
        "/impulse/api/incidents/inc-1/freeze", json={"until": deadline}
    )

    assert response.status_code == 200
    assert response.json() == {"success": True}
    until = datetime(2099, 8, 2, 18, tzinfo=UTC)
    assert actions.incident.frozen_until == until
    assert actions.incident.frozen_until_source == FreezeSource.TIME.value
    assert not actions.incident.chain_enabled
    actions.queue.put.assert_awaited_once_with(
        until, QueueItemType.UNFREEZE, "inc-1", data="time"
    )
    actions.messenger.update_incident_message.assert_awaited_once_with(actions.incident)
    actions.messenger.post_freeze_notification.assert_awaited_once()


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"until": None},
        {"until": 123},
        {"until": "tomorrow"},
        {"until": "123"},
        {"until": "2099-08-02"},
        {"until": "2099-08-02T18:00:00"},
        {"until": "2099-02-30T18:00:00Z"},
        {"until": "2099-08-02T18:00:00+99:99"},
    ],
)
def test_freeze_rejects_invalid_deadlines(actions, body):
    response = actions.client.post("/impulse/api/incidents/inc-1/freeze", json=body)
    assert response.status_code == 422
    assert not actions.incident.is_frozen
    actions.queue.put.assert_not_awaited()


def test_assign_and_unassign(actions):
    response = actions.client.post(
        "/impulse/api/incidents/inc-1/assign", json={"user_id": "U1"}
    )
    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert actions.incident.assigned_user_id == "U1"

    response = actions.client.post("/impulse/api/incidents/inc-1/unassign")
    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert actions.incident.assigned_user_id == ""
    assert actions.incident.chain_enabled


@pytest.mark.parametrize("body", [None, {}])
def test_unassign_accepts_empty_body_and_repeated_request(actions, body):
    actions.incident.assigned_user_id = "U1"
    response = actions.client.post("/impulse/api/incidents/inc-1/unassign", json=body)
    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert actions.incident.assigned_user_id == ""
    response = actions.client.post("/impulse/api/incidents/inc-1/unassign", json=body)
    assert response.status_code == 200
    assert response.json() == {"success": False}


@pytest.mark.parametrize("body", [{}, {"user_id": None}, {"user_id": 123}])
def test_assign_requires_string_id(actions, body):
    response = actions.client.post("/impulse/api/incidents/inc-1/assign", json=body)
    assert response.status_code == 422
    assert actions.incident.assigned_user_id == ""
    actions.queue.delete_by_id.assert_not_awaited()


@pytest.mark.parametrize("body", [None, {}])
def test_task_accepts_empty_body(actions, body):
    response = actions.client.post("/impulse/api/incidents/inc-1/task", json=body)
    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "result": {"task_link": "https://task/1"},
    }
    actions.messenger.task_management_integration.handle_button_press.assert_awaited_once_with(
        actions.incident, actions.queue
    )


@pytest.mark.parametrize("body", [None, {}])
def test_unfreeze_accepts_empty_body(actions, body):
    actions.incident.frozen_until = datetime(2099, 8, 2, 18, tzinfo=UTC)
    actions.incident.frozen_until_source = "time"
    response = actions.client.post("/impulse/api/incidents/inc-1/unfreeze", json=body)
    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert not actions.incident.is_frozen
    actions.queue.delete_by_id_and_type.assert_awaited_once_with(
        "inc-1", QueueItemType.UNFREEZE
    )
    actions.queue.recreate.assert_awaited_once_with(
        actions.incident.status, "inc-1", [], actions.incident.chain_active_seconds
    )


@pytest.mark.parametrize(
    "action, body",
    [
        ("freeze", {"until": "2099-08-02T18:00:00Z"}),
        ("task", {}),
        ("assign", {"user_id": "U1"}),
        ("unassign", {}),
        ("unfreeze", {}),
    ],
)
def test_actions_require_existing_incident(actions, action, body):
    response = actions.client.post(
        f"/impulse/api/incidents/missing/{action}", json=body
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Incident not found"}


@pytest.mark.parametrize(
    "action, body",
    [
        ("freeze", {"until": "2099-08-02T18:00:00Z"}),
        ("task", {}),
        ("assign", {"user_id": "U1"}),
        ("unassign", {}),
        ("unfreeze", {}),
    ],
)
def test_actions_require_authentication(actions, action, body):
    auth = Mock(
        session_cookie_name="session",
        get_current_user=Mock(return_value={"authenticated": False}),
    )
    app = FastAPI()
    app.state = actions.app.state
    app.include_router(create_router("", auth_manager=auth))
    response = TestClient(app).post(f"/api/incidents/inc-1/{action}", json=body)
    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}
    actions.queue.delete_by_id.assert_not_awaited()


def test_authenticated_freeze_assigns_actor(actions):
    user = {"id": "U1", "full_name": "Alice", "timezone": "Europe/Moscow"}
    auth = Mock(
        session_cookie_name="session",
        get_current_user=Mock(return_value={"authenticated": True, "user": user}),
    )
    app = FastAPI()
    app.state = actions.app.state
    app.include_router(create_router("", auth_manager=auth))
    client = TestClient(app)
    client.cookies.set("session", "session-1")
    response = client.post(
        "/api/incidents/inc-1/freeze", json={"until": "2099-08-02T18:00:00Z"}
    )
    assert response.status_code == 200
    assert actions.incident.assigned_user_id == "U1"
    auth.get_current_user.assert_called_once_with(session_id="session-1")
    actions.messenger.post_freeze_notification.assert_awaited_once_with(
        actions.incident, ui_user=user
    )


@pytest.mark.parametrize(
    "field, value, action",
    [
        ("task_link", "https://task/1", "task"),
        ("task_creation_in_progress", True, "task"),
        ("frozen_until", datetime(2099, 8, 2, tzinfo=UTC), "freeze"),
        ("frozen_until_source", "maintenance", "unfreeze"),
        ("parents", ["parent-1"], "unfreeze"),
    ],
)
def test_conflicts_preserve_incident_state(actions, field, value, action):
    if action == "unfreeze":
        actions.incident.frozen_until = datetime(2099, 8, 2, tzinfo=UTC)
        actions.incident.frozen_until_source = "time"
    setattr(actions.incident, field, value)
    response = actions.client.post(
        f"/impulse/api/incidents/inc-1/{action}", json={"until": "2099-08-02T18:00:00Z"}
    )
    assert response.status_code == 409
    assert getattr(actions.incident, field) == value
    actions.incident.dump.assert_not_called()
    actions.queue.put.assert_not_awaited()


@pytest.mark.parametrize("action", ["task", "freeze", "unfreeze", "assign", "unassign"])
def test_actions_only_accept_post(actions, action):
    assert (
        actions.client.get(f"/impulse/api/incidents/inc-1/{action}").status_code == 405
    )
    actions.incident.dump.assert_not_called()


@pytest.mark.parametrize("action", ["task", "freeze", "unfreeze", "assign", "unassign"])
def test_actions_are_blocked_on_standby(actions, action):
    actions.app.state.is_standby = True
    actions.app.add_middleware(StandbyMiddleware)
    response = actions.client.post(f"/impulse/api/incidents/inc-1/{action}")
    assert response.status_code == 503
    actions.incident.dump.assert_not_called()


@pytest.mark.parametrize(
    "action, body",
    [
        ("task", {}),
        ("assign", {"user_id": "U1"}),
        ("assign", {"user_id": ""}),
        ("unfreeze", {}),
    ],
)
def test_legacy_actions_share_results_and_missing_id_errors(actions, action, body):
    if action == "unfreeze":
        actions.incident.frozen_until = datetime(2099, 8, 2, tzinfo=UTC)
        actions.incident.frozen_until_source = "time"
    response = actions.client.post(
        f"/impulse/{action}", json={"uniq_id": "inc-1", **body}
    )
    assert response.status_code == 200
    assert response.json()["success"] is (action != "assign" or body["user_id"] != "")
    response = actions.client.post(f"/impulse/{action}", json=body)
    assert response.status_code == 400
    assert response.json() == {"detail": "uniq_id is required"}


def test_legacy_freeze_preserves_presets(actions, monkeypatch):
    until = datetime(2099, 8, 2, 18, tzinfo=UTC)
    calculate = Mock(return_value=until)
    monkeypatch.setattr("app.im.application.calculate_freeze_time", calculate)
    response = actions.client.post(
        "/impulse/freeze", json={"uniq_id": "inc-1", "freeze_option": "tomorrow"}
    )
    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert actions.incident.frozen_until == until
    assert calculate.call_args.args[0] == "tomorrow"


def test_assignment_users_matches_api_users(actions):
    legacy = actions.client.get("/impulse/assignment_users")
    assert legacy.status_code == 200
    assert legacy.json() == actions.client.get("/impulse/api/users").json()


def test_legacy_incidents_matches_api_incidents(actions):
    actions.app.state.incidents.serialize.return_value = {"inc-1": {"uniq_id": "inc-1"}}
    assert (
        actions.client.get("/impulse/incidents").json()
        == actions.client.get("/impulse/api/incidents").json()
    )
