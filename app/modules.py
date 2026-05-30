import inspect
from importlib.metadata import entry_points
from typing import Any, Callable, Dict, List, Mapping, Optional

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.logging import logger


HookCallback = Callable[[Mapping[str, Any]], Any]
MessageHandler = Callable[..., Any]

MODULE_ENTRY_POINT_GROUP = "impulse.modules"

_module_host: Optional["ModuleHost"] = None


class ModuleMessageError(Exception):
    """Raised when a websocket module_message cannot be handled."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class ModuleHost:
    """Runtime API backing every installed IMPulse module.

    Modules never receive this host directly; each module is handed a
    :class:`ModuleApi` bound to its own name so registrations are namespaced.
    """

    def __init__(self, app: FastAPI, context: Mapping[str, Any]):
        self.app = app
        self.context = dict(context)
        self.http_prefix = (context.get("http_prefix") or "").rstrip("/")
        self.hooks: Dict[str, List[HookCallback]] = {}
        self.message_handlers: Dict[str, Dict[str, MessageHandler]] = {}
        self.frontend_modules: List[dict] = []

    # --- lifecycle hooks (fire-and-forget) ---------------------------------

    def register_hook(self, event_name: str, callback: HookCallback):
        self.hooks.setdefault(event_name, []).append(callback)
        logger.info("Registered module hook", extra={"event_name": event_name})

    def dispatch_hook(self, event_name: str, payload: Mapping[str, Any]):
        callbacks = list(self.hooks.get(event_name, []))
        callbacks.extend(self.hooks.get("*", []))

        for callback in callbacks:
            try:
                result = callback(payload)
                if inspect.isawaitable(result):
                    self._schedule_callback(result, event_name)
            except Exception as e:
                logger.error("Module hook failed", extra={"event_name": event_name, "error": str(e)})

    # --- request/response module messages (websocket) ----------------------

    def register_module_message_handler(self, module_name: str, hook_name: str, handler: MessageHandler):
        self.message_handlers.setdefault(module_name, {})[hook_name] = handler
        logger.info(
            "Registered module message handler",
            extra={"module_name": module_name, "hook": hook_name},
        )

    async def dispatch_module_message(self, module_name: str, hook_name: str, params: Mapping[str, Any]):
        """Invoke a module message handler and return its serializable result.

        Raises :class:`ModuleMessageError` when no handler is registered or the
        handler fails, so the websocket layer can build an error response.
        """
        handler = self.message_handlers.get(module_name, {}).get(hook_name)
        if handler is None:
            raise ModuleMessageError(
                "unknown_hook",
                f"No message handler for module '{module_name}' hook '{hook_name}'",
            )

        try:
            result = handler(dict(params) if params else {})
            if inspect.isawaitable(result):
                result = await result
            return result
        except ModuleMessageError:
            raise
        except Exception as e:
            logger.error(
                "Module message handler failed",
                extra={"module_name": module_name, "hook": hook_name, "error": str(e)},
            )
            raise ModuleMessageError("handler_error", str(e))

    # --- routers ------------------------------------------------------------

    def register_router(self, module_name: str, router):
        prefix = f"{self.http_prefix}/api/module/{module_name}"
        self.app.include_router(router, prefix=prefix)
        logger.info("Registered module router", extra={"module_name": module_name, "prefix": prefix})

    # --- frontend modules ---------------------------------------------------

    def register_frontend_module(self, module_name: str, manifest: dict, assets_dir: str):
        """Mount a module's static asset directory and derive its public URLs.

        The module ships its JS/CSS as package data and only declares the
        filenames (`script` / `style`); OSS serves them from a single
        `StaticFiles` mount under `{http_prefix}/api/module/{module_name}/static`
        and fills in `script_url` / `style_url` so the URLs are always
        `http_prefix`-correct. The mount lives under the module's own
        `api/module/{module_name}` namespace to avoid shadowing by the core
        `{http_prefix}/static` mount (Starlette matches mounts in registration
        order, longest-prefix is not preferred).
        """
        mount_path = f"{self.http_prefix}/api/module/{module_name}/static"
        self.app.mount(
            mount_path,
            StaticFiles(directory=str(assets_dir)),
            name=f"module-static-{module_name}",
        )

        normalized = dict(manifest)
        normalized["module"] = module_name
        if normalized.get("script"):
            normalized["script_url"] = f"{mount_path}/{normalized['script']}"
        if normalized.get("style"):
            normalized["style_url"] = f"{mount_path}/{normalized['style']}"
        self.frontend_modules.append(normalized)
        logger.info(
            "Registered frontend module",
            extra={"module_name": module_name, "module_id": normalized.get("module_id"), "mount": mount_path},
        )

    def get_frontend_modules(self) -> List[dict]:
        """Return browser-facing frontend module manifests."""
        manifests = []
        for manifest in self.frontend_modules:
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
                logger.warning("Async module hook skipped because no event loop is running", extra={"event_name": event_name})
                return

            task = asyncio.create_task(awaitable)

            def _log_failure(done_task):
                try:
                    done_task.result()
                except Exception as e:
                    logger.error("Async module hook failed", extra={"event_name": event_name, "error": str(e)})

            task.add_done_callback(_log_failure)
        except RuntimeError:
            logger.warning("Async module hook skipped because no event loop is available", extra={"event_name": event_name})


class ModuleApi:
    """Module-scoped registration surface handed to each module.

    The module name is discovered by IMPulse from the loaded entry point, so
    every router, message handler, and frontend manifest is automatically
    namespaced under that module without the module having to declare it.
    """

    def __init__(self, host: ModuleHost, module_name: str):
        self._host = host
        self.module_name = module_name
        self.context = host.context

    def register_hook(self, event_name: str, callback: HookCallback):
        self._host.register_hook(event_name, callback)

    def register_router(self, router):
        self._host.register_router(self.module_name, router)

    def register_module_message_handler(self, hook_name: str, handler: MessageHandler):
        self._host.register_module_message_handler(self.module_name, hook_name, handler)

    def register_frontend_module(self, manifest: dict, assets_dir: str):
        self._host.register_frontend_module(self.module_name, manifest, assets_dir)


def load_modules(app: FastAPI, env_config, config, auth_manager=None) -> ModuleHost:
    """Load configured module entry points from the impulse.modules group."""
    global _module_host

    context = {
        "data_root": env_config.data_path,
        "http_prefix": env_config.http_prefix,
        "config_path": env_config.config_path,
        "config": config,
        "auth_manager": auth_manager,
    }
    host = ModuleHost(app=app, context=context)
    _module_host = host
    app.state.module_host = host

    enabled_modules = set(env_config.modules)
    if not enabled_modules:
        logger.info("No IMPulse modules configured")
        return host

    discovered = {entry_point.name: entry_point for entry_point in entry_points(group=MODULE_ENTRY_POINT_GROUP)}
    for module_name in sorted(enabled_modules):
        entry_point = discovered.get(module_name)
        if entry_point is None:
            logger.warning("Configured IMPulse module was not found", extra={"module_name": module_name})
            continue

        try:
            register_module = entry_point.load()
            module_api = ModuleApi(host=host, module_name=module_name)
            register_module(module_api, context=dict(context))
            logger.info("Loaded IMPulse module", extra={"module_name": module_name})
        except Exception as e:
            logger.error("Failed to load IMPulse module", extra={"module_name": module_name, "error": str(e)})

    return host


def get_module_host() -> Optional[ModuleHost]:
    return _module_host


def incident_hook_payload(
    uniq_id: str,
    *,
    actor_id: Any = None,
    **extra: Any,
) -> dict[str, Any]:
    """Build a generic module hook payload keyed by incident occurrence id."""
    payload: dict[str, Any] = {"uniq_id": uniq_id}
    if actor_id is not None:
        payload["actor_id"] = actor_id
    if extra:
        payload.update(extra)
    return payload


def dispatch_hook(event_name: str, payload: Mapping[str, Any]):
    host = get_module_host()
    if host is None:
        return
    host.dispatch_hook(event_name=event_name, payload=payload)
