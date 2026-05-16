import inspect
from importlib.metadata import entry_points
from typing import Any, Callable, Dict, List, Mapping, Optional

from fastapi import FastAPI

from app.logging import logger


HookCallback = Callable[[Mapping[str, Any]], Any]

_extension_host: Optional["ExtensionHost"] = None


class ExtensionHost:
    """Runtime API exposed to installed IMPulse extensions."""

    def __init__(self, app: FastAPI, context: Mapping[str, Any]):
        self.app = app
        self.context = dict(context)
        self.hooks: Dict[str, List[HookCallback]] = {}
        self.frontend_extensions: List[dict] = []

    def register_hook(self, event_name: str, callback: HookCallback):
        self.hooks.setdefault(event_name, []).append(callback)
        logger.info("Registered extension hook", extra={"event_name": event_name})

    def dispatch_hook(self, event_name: str, payload: Mapping[str, Any]):
        callbacks = list(self.hooks.get(event_name, []))
        callbacks.extend(self.hooks.get("*", []))

        for callback in callbacks:
            try:
                result = callback(payload)
                if inspect.isawaitable(result):
                    self._schedule_callback(result, event_name)
            except Exception as e:
                logger.error("Extension hook failed", extra={"event_name": event_name, "error": str(e)})

    def register_router(self, router):
        self.app.include_router(router)
        logger.info("Registered extension router")

    def register_frontend_extension(self, manifest: dict):
        self.frontend_extensions.append(manifest)
        logger.info("Registered frontend extension", extra={"extension_id": manifest.get("extension_id")})

    def get_frontend_extensions(self) -> List[dict]:
        """Return browser-facing frontend extension manifests."""
        manifests = []
        for manifest in self.frontend_extensions:
            normalized = dict(manifest)
            mount_point = normalized.get("mount_point")
            if mount_point and "mount_points" not in normalized:
                normalized["mount_points"] = [mount_point]
            manifests.append(normalized)
        return manifests

    @staticmethod
    def _schedule_callback(awaitable, event_name: str):
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if not loop.is_running():
                logger.warning("Async extension hook skipped because no event loop is running", extra={"event_name": event_name})
                return

            task = asyncio.create_task(awaitable)

            def _log_failure(done_task):
                try:
                    done_task.result()
                except Exception as e:
                    logger.error("Async extension hook failed", extra={"event_name": event_name, "error": str(e)})

            task.add_done_callback(_log_failure)
        except RuntimeError:
            logger.warning("Async extension hook skipped because no event loop is available", extra={"event_name": event_name})


def load_extensions(app: FastAPI, env_config, config, auth_manager=None) -> ExtensionHost:
    """Load configured extension entry points from the impulse.extensions group."""
    global _extension_host

    context = {
        "data_root": env_config.data_path,
        "http_prefix": env_config.http_prefix,
        "config_path": env_config.config_path,
        "config": config,
        "auth_manager": auth_manager,
    }
    host = ExtensionHost(app=app, context=context)
    _extension_host = host
    app.state.extension_host = host

    enabled_extensions = set(env_config.extensions)
    if not enabled_extensions:
        logger.info("No IMPulse extensions configured")
        return host

    discovered = {entry_point.name: entry_point for entry_point in entry_points(group="impulse.extensions")}
    for extension_name in sorted(enabled_extensions):
        entry_point = discovered.get(extension_name)
        if entry_point is None:
            logger.warning("Configured IMPulse extension was not found", extra={"extension": extension_name})
            continue

        try:
            register_extension = entry_point.load()
            register_extension(host, context=dict(context))
            logger.info("Loaded IMPulse extension", extra={"extension": extension_name})
        except Exception as e:
            logger.error("Failed to load IMPulse extension", extra={"extension": extension_name, "error": str(e)})

    return host


def get_extension_host() -> Optional[ExtensionHost]:
    return _extension_host


def dispatch_hook(event_name: str, payload: Mapping[str, Any]):
    host = get_extension_host()
    if host is None:
        return
    host.dispatch_hook(event_name=event_name, payload=payload)


