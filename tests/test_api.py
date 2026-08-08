from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.im.groups import Group
from app.im.user_groups import UserGroup
from app.im.users import UserManager
from app.im.user_store import UserStore
from app.im.slack.user import User as SlackUser
from app.routes import create_router
from app.webhook import Webhook


def _make_api_client(**state_overrides):
    app = FastAPI()
    app.state.incidents = state_overrides.get("incidents", Mock())
    app.state.messenger = state_overrides.get("messenger", Mock())
    app.state.webhooks = state_overrides.get("webhooks", {})
    app.include_router(create_router(""))
    return TestClient(app)


@pytest.fixture
def sample_group():
    return Group("team-a", name="Team A", id_="G123", exists=True)


@pytest.fixture
def sample_user():
    return SlackUser("alice", id_="U123", exists=True, full_name="Alice", username="alice")


@pytest.fixture
def stored_user():
    return SlackUser(None, id_="U999", exists=True, full_name="Stored User", username="stored")


@pytest.fixture
def sample_user_group(sample_user):
    return UserGroup("ops", [sample_user])


@pytest.fixture
def sample_webhook():
    return Webhook(
        url="https://example.com/hook",
        data={"text": "hello"},
        json_payload=None,
        auth="user:pass",
    )


@pytest.fixture
def api_client(sample_group, sample_user, stored_user, sample_user_group, sample_webhook):
    users = UserManager()
    users.add_user("U123", sample_user, config_name="alice")
    users.add_user("U999", stored_user)

    incidents = Mock()
    incidents.serialize.return_value = {"inc-1": {"uniq_id": "inc-1", "status": "firing"}}
    incident = Mock()
    incident.serialize.return_value = {"uniq_id": "inc-1", "status": "firing"}
    incidents.get_by_uniq_id.side_effect = lambda uniq_id: incident if uniq_id == "inc-1" else None

    messenger = Mock()
    messenger.groups = {"team-a": sample_group}
    messenger.users = users
    messenger.user_groups = {"ops": sample_user_group}

    return _make_api_client(
        incidents=incidents,
        messenger=messenger,
        webhooks={"notify": sample_webhook},
    )


class TestEntitySerialize:
    def test_group_serialize(self, sample_group):
        payload = sample_group.serialize()
        assert payload == {
            "exists": True,
            "id": "G123",
        }
        assert list(payload) == sorted(payload)

    def test_user_serialize(self, sample_user):
        payload = sample_user.serialize()
        assert payload == {
            "email": None,
            "full_name": "Alice",
            "id": "U123",
            "name": "alice",
            "timezone": None,
            "username": "alice",
        }
        assert list(payload) == sorted(payload)
        assert isinstance(payload["id"], str)

    def test_user_group_serialize(self, sample_user_group):
        assert sample_user_group.serialize() == {
            "users": ["alice"],
        }

    def test_webhook_serialize(self, sample_webhook):
        payload = sample_webhook.serialize()
        assert payload == {
            "data": {"text": "hello"},
            "json": None,
            "url": "https://example.com/hook",
        }
        assert list(payload) == sorted(payload)

    def test_webhook_serialize_preserves_url_template(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_HOST", "secret.example.com")
        webhook = Webhook("https://{{ env.WEBHOOK_HOST }}/hook", auth="user:pass")

        payload = webhook.serialize()
        assert payload == {
            "data": None,
            "json": None,
            "url": "https://{{ env.WEBHOOK_HOST }}/hook",
        }
        assert list(payload) == sorted(payload)

    def test_user_store_serialize_matches_save_payload(self):
        updated_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        user_data = {
            "username": "alice",
            "email": "alice@example.com",
            "full_name": "Alice",
            "timezone": "UTC",
        }
        payload = UserStore.serialize("slack", user_data, updated_at=updated_at)
        assert payload == {
            "email": "alice@example.com",
            "full_name": "Alice",
            "messenger_type": "slack",
            "timezone": "UTC",
            "updated_at": updated_at,
            "username": "alice",
        }
        assert list(payload) == sorted(payload)

    def test_user_manager_serialize_configured_only(self, sample_user, stored_user):
        users = UserManager()
        users.add_user("U123", sample_user, config_name="alice")
        users.add_user("U999", stored_user)

        assert users.serialize() == [sample_user.serialize()]
        assert users.serialize_one("alice") == sample_user.serialize()
        assert users.serialize_one("U999") is None


class TestIncidentsApi:
    def test_list_incidents(self, api_client):
        response = api_client.get("/api/incidents")
        assert response.status_code == 200
        assert response.json() == {"inc-1": {"uniq_id": "inc-1", "status": "firing"}}

    def test_get_incident(self, api_client):
        response = api_client.get("/api/incidents/inc-1")
        assert response.status_code == 200
        assert response.json() == {"uniq_id": "inc-1", "status": "firing"}

    def test_get_incident_not_found(self, api_client):
        response = api_client.get("/api/incidents/missing")
        assert response.status_code == 404
        assert response.json()["detail"] == "Incident not found"


class TestGroupsApi:
    def test_list_groups(self, api_client, sample_group):
        response = api_client.get("/api/groups")
        assert response.status_code == 200
        assert response.json() == {"team-a": sample_group.serialize()}

    def test_get_group(self, api_client, sample_group):
        response = api_client.get("/api/groups/team-a")
        assert response.status_code == 200
        assert response.json() == sample_group.serialize()

    def test_get_group_not_found(self, api_client):
        response = api_client.get("/api/groups/missing")
        assert response.status_code == 404
        assert response.json()["detail"] == "Group not found"


class TestUsersApi:
    def test_list_users_configured_only(self, api_client, sample_user):
        response = api_client.get("/api/users")
        assert response.status_code == 200
        assert response.json() == [sample_user.serialize()]

    def test_get_user(self, api_client, sample_user):
        response = api_client.get("/api/users/alice")
        assert response.status_code == 200
        assert response.json() == sample_user.serialize()

    def test_get_runtime_user_by_id_not_found(self, api_client):
        response = api_client.get("/api/users/U999")
        assert response.status_code == 404
        assert response.json()["detail"] == "User not found"

    def test_get_user_not_found(self, api_client):
        response = api_client.get("/api/users/missing")
        assert response.status_code == 404
        assert response.json()["detail"] == "User not found"


class TestUserGroupsApi:
    def test_list_user_groups(self, api_client, sample_user_group):
        response = api_client.get("/api/user_groups")
        assert response.status_code == 200
        assert response.json() == {"ops": sample_user_group.serialize()}

    def test_get_user_group(self, api_client, sample_user_group):
        response = api_client.get("/api/user_groups/ops")
        assert response.status_code == 200
        assert response.json() == sample_user_group.serialize()

    def test_get_user_group_not_found(self, api_client):
        response = api_client.get("/api/user_groups/missing")
        assert response.status_code == 404
        assert response.json()["detail"] == "User group not found"


class TestWebhooksApi:
    def test_list_webhooks(self, api_client, sample_webhook):
        response = api_client.get("/api/webhooks")
        assert response.status_code == 200
        assert response.json() == {"notify": sample_webhook.serialize()}

    def test_get_webhook(self, api_client, sample_webhook):
        response = api_client.get("/api/webhooks/notify")
        assert response.status_code == 200
        assert response.json() == sample_webhook.serialize()

    def test_get_webhook_not_found(self, api_client):
        response = api_client.get("/api/webhooks/missing")
        assert response.status_code == 404
        assert response.json()["detail"] == "Webhook not found"
