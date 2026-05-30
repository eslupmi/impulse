"""
Unit tests for app.modules module.
"""
import asyncio
from unittest.mock import Mock

import pytest
from fastapi import APIRouter, FastAPI

from app import modules


class _EntryPoint:
    """Fake importlib.metadata entry point for module loading tests."""

    def __init__(self, name, register):
        self.name = name
        self._register = register

    def load(self):
        return self._register


class TestModuleLoading:
    """Test cases for configured module entry point loading."""

    @pytest.fixture
    def fastapi_app(self):
        """Create a FastAPI app for module host tests."""
        return FastAPI()

    @pytest.fixture
    def env_config(self):
        """Create mock environment config with one enabled module."""
        config = Mock()
        config.modules = ["enabled_module"]
        config.data_path = "/tmp/impulse-data"
        config.http_prefix = "/impulse"
        config.config_path = "/tmp/impulse-config"
        return config

    def test_load_modules_only_loads_configured_entry_points(self, monkeypatch, fastapi_app, env_config):
        """Test that only modules listed in MODULES are loaded."""
        loaded = []

        def register_module(module_api, context):
            loaded.append((module_api, context))

        monkeypatch.setattr(
            modules,
            "entry_points",
            lambda group: [
                _EntryPoint("enabled_module", register_module),
                _EntryPoint("disabled_module", lambda *_: loaded.append("disabled")),
            ],
        )

        host = modules.load_modules(
            app=fastapi_app, env_config=env_config, config=object(), auth_manager=None
        )

        assert host is fastapi_app.state.module_host
        assert len(loaded) == 1
        module_api, context = loaded[0]
        assert module_api.module_name == "enabled_module"
        assert context["data_root"] == "/tmp/impulse-data"
        assert context["http_prefix"] == "/impulse"
        assert context["auth_manager"] is None

    def test_load_modules_passes_auth_manager_in_context(self, monkeypatch, fastapi_app, env_config):
        loaded = []

        def register_module(module_api, context):
            loaded.append(context)

        monkeypatch.setattr(
            modules,
            "entry_points",
            lambda group: [_EntryPoint("enabled_module", register_module)],
        )

        auth = Mock()
        modules.load_modules(
            app=fastapi_app, env_config=env_config, config=object(), auth_manager=auth
        )

        assert loaded[0]["auth_manager"] is auth


class TestModuleHost:
    """Test cases for ModuleHost registration and dispatch behavior."""

    @pytest.fixture
    def fastapi_app(self):
        """Create a FastAPI app for module host tests."""
        return FastAPI()

    @pytest.fixture
    def module_host(self, fastapi_app):
        """Create a module host for tests."""
        return modules.ModuleHost(app=fastapi_app, context={"http_prefix": ""})

    def test_dispatches_hooks_and_mounts_routers_under_module_path(self, fastapi_app, module_host):
        """Routers are mounted under api/module/{module_name} and hooks dispatch."""
        received = []
        router = APIRouter()

        @router.get("/ping")
        def ping():
            return {"ok": True}

        module_host.register_router("impulse_ee", router)
        module_host.register_hook("incident.created", received.append)
        module_host.dispatch_hook("incident.created", {"uniq_id": "incident-1"})

        assert received == [{"uniq_id": "incident-1"}]
        assert any(route.path == "/api/module/impulse_ee/ping" for route in fastapi_app.routes)

    def test_router_prefix_respects_http_prefix(self, fastapi_app):
        host = modules.ModuleHost(app=fastapi_app, context={"http_prefix": "/impulse"})
        router = APIRouter()

        @router.get("/ping")
        def ping():
            return {"ok": True}

        host.register_router("impulse_ee", router)
        assert any(route.path == "/impulse/api/module/impulse_ee/ping" for route in fastapi_app.routes)

    def test_frontend_modules_are_returned_as_normalized_copies(self, module_host):
        """Frontend module manifests are exposed to the UI safely."""
        manifest = {
            "module_id": "impulse_ee.history",
            "mount_point": "incident.row.dropdown.actions",
            "script_url": "/api/module/impulse_ee/history.js",
        }

        module_host.register_frontend_module("impulse_ee", manifest)
        manifests = module_host.get_frontend_modules()
        manifests[0]["module_id"] = "mutated"

        assert manifests[0]["mount_points"] == ["incident.row.dropdown.actions"]
        assert manifests[0]["module"] == "impulse_ee"
        assert module_host.frontend_modules[0]["module_id"] == "impulse_ee.history"

    def test_module_message_handler_returns_data(self, module_host):
        module_host.register_module_message_handler(
            "impulse_ee", "incident_history", lambda params: {"uniq_id": params["uniq_id"], "events": []}
        )

        result = asyncio.run(
            module_host.dispatch_module_message("impulse_ee", "incident_history", {"uniq_id": "occ-1"})
        )

        assert result == {"uniq_id": "occ-1", "events": []}

    def test_module_message_unknown_hook_raises(self, module_host):
        with pytest.raises(modules.ModuleMessageError) as exc:
            asyncio.run(module_host.dispatch_module_message("impulse_ee", "missing", {}))
        assert exc.value.code == "unknown_hook"

    def test_module_message_handler_error_is_wrapped(self, module_host):
        def boom(_params):
            raise ValueError("kaboom")

        module_host.register_module_message_handler("impulse_ee", "boom", boom)
        with pytest.raises(modules.ModuleMessageError) as exc:
            asyncio.run(module_host.dispatch_module_message("impulse_ee", "boom", {}))
        assert exc.value.code == "handler_error"

    def test_module_dispatch_hook_delegates_to_module_host(self, monkeypatch, module_host):
        """Module-level dispatch_hook delegates to the active host."""
        received = []
        module_host.register_hook("incident.status_changed", received.append)
        monkeypatch.setattr(modules, "_module_host", module_host)

        modules.dispatch_hook(
            "incident.status_changed",
            {"uniq_id": "occurrence-1"},
        )

        assert received[0]["uniq_id"] == "occurrence-1"
