"""
Unit tests for app.extensions module.
"""
from unittest.mock import Mock

import pytest
from fastapi import APIRouter, FastAPI

from app import extensions


class _EntryPoint:
    """Fake importlib.metadata entry point for extension loading tests."""

    def __init__(self, name, register):
        self.name = name
        self._register = register

    def load(self):
        return self._register


class TestExtensionLoading:
    """Test cases for configured extension entry point loading."""

    @pytest.fixture
    def fastapi_app(self):
        """Create a FastAPI app for extension host tests."""
        return FastAPI()

    @pytest.fixture
    def env_config(self):
        """Create mock environment config with one enabled extension."""
        config = Mock()
        config.extensions = ["enabled_ext"]
        config.data_path = "/tmp/impulse-data"
        config.http_prefix = "/impulse"
        config.config_path = "/tmp/impulse-config"
        return config

    def test_load_extensions_only_loads_configured_entry_points(self, monkeypatch, fastapi_app, env_config):
        """Test that only extensions listed in EXTENSIONS are loaded."""
        loaded = []

        def register_extension(host, context):
            loaded.append((host, context))

        monkeypatch.setattr(
            extensions,
            "entry_points",
            lambda group: [
                _EntryPoint("enabled_ext", register_extension),
                _EntryPoint("disabled_ext", lambda *_: loaded.append("disabled")),
            ],
        )

        host = extensions.load_extensions(app=fastapi_app, env_config=env_config, config=object())

        assert host is fastapi_app.state.extension_host
        assert len(loaded) == 1
        assert loaded[0][1]["data_root"] == "/tmp/impulse-data"
        assert loaded[0][1]["http_prefix"] == "/impulse"


class TestExtensionHost:
    """Test cases for ExtensionHost registration and dispatch behavior."""

    @pytest.fixture
    def fastapi_app(self):
        """Create a FastAPI app for extension host tests."""
        return FastAPI()

    @pytest.fixture
    def extension_host(self, fastapi_app):
        """Create an extension host for tests."""
        return extensions.ExtensionHost(app=fastapi_app, context={})

    def test_dispatches_hooks_and_includes_routers(self, fastapi_app, extension_host):
        """Test hook dispatch and extension router registration."""
        received = []
        router = APIRouter(prefix="/ext")

        @router.get("/ping")
        def ping():
            return {"ok": True}

        extension_host.register_router(router)
        extension_host.register_hook("incident.created", received.append)
        extension_host.dispatch_hook("incident.created", {"incident_id": "incident-1"})

        assert received == [{"incident_id": "incident-1"}]
        assert any(route.path == "/ext/ping" for route in fastapi_app.routes)

    def test_module_dispatch_hook_delegates_to_extension_host(self, monkeypatch, extension_host):
        """Test module-level dispatch_hook delegates to the active host."""
        received = []
        extension_host.register_hook("incident.status_changed", received.append)
        monkeypatch.setattr(extensions, "_extension_host", extension_host)

        extensions.dispatch_hook(
            "incident.status_changed",
            {"incident_id": "occurrence-1", "incident_uuid": "group-1"},
        )

        assert received[0]["incident_id"] == "occurrence-1"
        assert received[0]["incident_uuid"] == "group-1"
