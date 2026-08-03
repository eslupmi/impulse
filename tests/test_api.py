from unittest.mock import Mock, patch
from datetime import datetime, timezone

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
        assert sample_group.serialize() == {
            "name": "Team A",
            "id": "G123",
            "exists": True,
            "is_defined": True,
        }

    def test_user_serialize(self, sample_user):
        assert sample_user.serialize() == {
            "id": "U123",
            "username": "alice",
            "full_name": "Alice",
            "timezone": None,
            "is_defined": True,
        }

    def test_user_group_serialize(self, sample_user_group):
        assert sample_user_group.serialize() == {
            "users": ["alice"],
            "is_defined": True,
        }

    def test_webhook_serialize(self, sample_webhook):
        assert sample_webhook.serialize() == {
            "url": "https://example.com/hook",
            "data": {"text": "hello"},
            "json": None,
            "is_defined": True,
        }

    def test_webhook_serialize_preserves_url_template(self, monkeypatch):
        monkeypatch.setenv("WEBHOOK_HOST", "secret.example.com")
        webhook = Webhook("https://{{ env.WEBHOOK_HOST }}/hook", auth="user:pass")

        assert webhook.serialize() == {
            "url": "https://{{ env.WEBHOOK_HOST }}/hook",
            "data": None,
            "json": None,
            "is_defined": True,
        }

    def test_user_store_serialize_matches_save_payload(self):
        updated_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        user_data = {
            "username": "alice",
            "email": "alice@example.com",
            "full_name": "Alice",
            "timezone": "UTC",
        }
        assert UserStore.serialize("slack", user_data, updated_at=updated_at) == {
            "updated_at": updated_at,
            "messenger_type": "slack",
            "username": "alice",
            "email": "alice@example.com",
            "full_name": "Alice",
            "timezone": "UTC",
        }

    def test_user_manager_serialize_prefers_disk_content(self, sample_user, stored_user):
        users = UserManager()
        users.add_user("U123", sample_user, config_name="alice")
        users.add_user("U999", stored_user)
        disk_payload = {
            "updated_at": datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
            "messenger_type": "slack",
            "username": "alice",
            "email": "alice@example.com",
            "full_name": "Alice",
            "timezone": "UTC",
        }
        store = Mock()
        store.get_all.return_value = {"U123": disk_payload}
        store.get.side_effect = lambda user_id: disk_payload if user_id == "U123" else None

        with patch("app.im.users.get_user_store", return_value=store):
            assert users.serialize() == {
                "alice": {
                    **disk_payload,
                    "id": "U123",
                    "is_defined": True,
                },
                "U999": stored_user.serialize(),
            }
            assert users.serialize_one("alice") == {
                **disk_payload,
                "id": "U123",
                "is_defined": True,
            }
            assert users.serialize_one("U999") == stored_user.serialize()
        store.get_all.assert_called_once_with()


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
    def test_list_users(self, api_client, sample_user, stored_user):
        store = Mock()
        store.get_all.return_value = {}
        store.get.return_value = None
        with patch("app.im.users.get_user_store", return_value=store):
            response = api_client.get("/api/users")
        assert response.status_code == 200
        assert response.json() == {
            "alice": sample_user.serialize(),
            "U999": stored_user.serialize(),
        }

    def test_list_users_returns_disk_content_when_present(self, api_client):
        disk_payload = {
            "updated_at": "2026-01-02T03:04:05+00:00",
            "messenger_type": "slack",
            "username": "alice",
            "email": "alice@example.com",
            "full_name": "Alice",
            "timezone": "UTC",
        }
        store = Mock()
        store.get_all.return_value = {"U123": disk_payload}
        with patch("app.im.users.get_user_store", return_value=store):
            response = api_client.get("/api/users")
        assert response.status_code == 200
        assert response.json()["alice"] == {
            **disk_payload,
            "id": "U123",
            "is_defined": True,
        }

    def test_get_user(self, api_client, sample_user):
        store = Mock()
        store.get.return_value = None
        with patch("app.im.users.get_user_store", return_value=store):
            response = api_client.get("/api/users/alice")
        assert response.status_code == 200
        assert response.json() == sample_user.serialize()

    def test_get_stored_user_by_id(self, api_client, stored_user):
        store = Mock()
        store.get.return_value = None
        with patch("app.im.users.get_user_store", return_value=store):
            response = api_client.get("/api/users/U999")
        assert response.status_code == 200
        assert response.json() == stored_user.serialize()

    def test_get_user_not_found(self, api_client):
        store = Mock()
        store.get.return_value = None
        with patch("app.im.users.get_user_store", return_value=store):
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
