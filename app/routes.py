import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config.config import get_config, reload_config
from app.logging import logger
from app.maintenance.api import removed_windows, windows_from_ws_payload
from app.maintenance.store import get_maintenance_store
from app.metrics import generate_metrics_response
from app.middleware import is_standby_mode, service_unavailable_response, STANDBY_MODE_MESSAGE
from app.ui.table_config import get_all_ui_config
from app.ui.websocket import incident_ws
from app.im.chain.ui_chains_store import ui_chains_store


_MSG_INCIDENT_NOT_FOUND = "Incident not found"
_MSG_UNIQ_ID_REQUIRED = "uniq_id is required"
_MSG_AUTHENTICATION_REQUIRED = "Authentication required"


async def _maintenance_save_side_effects(app, existing, saved, deleted):
    try:
        await app.state.maintenance_manager.apply_save_side_effects(existing, saved, deleted)
    except Exception as e:
        logger.error("Maintenance save side effects failed", extra={"error": str(e)})


def create_router(http_prefix: str, fastapi_app: FastAPI = None, auth_manager=None) -> APIRouter:
    router = APIRouter(prefix=http_prefix)

    templates = None
    if fastapi_app and get_config().ui_config:
        fastapi_app.mount(f"{http_prefix}/static", StaticFiles(directory="static"), name="static")
        templates = Jinja2Templates(directory="templates")

    @router.get("/livez")
    def get_live(request: Request):
        return Response(
            status_code=200,
            content="OK",
            media_type="text/plain"
        )

    @router.get("/readyz")
    def get_ready(request: Request):
        if not hasattr(request.app, 'state'):
            return service_unavailable_response("Service Unavailable - Initializing")

        if is_standby_mode(request.app.state):
            return service_unavailable_response(STANDBY_MODE_MESSAGE)

        if not hasattr(request.app.state, 'queue') or not hasattr(request.app.state, 'queue_manager'):
            return service_unavailable_response("Service Unavailable - Initializing")

        return Response(
            status_code=200,
            content="OK",
            media_type="text/plain"
        )

    @router.get("/metrics")
    async def get_metrics(request: Request):
        queue = request.app.state.queue
        return await generate_metrics_response(queue)

    if templates:
        @router.get("/", response_class=HTMLResponse)
        async def get_index(request: Request):
            return templates.TemplateResponse("index.html", {
                "request": request,
                "http_prefix": http_prefix
            })

    @router.get("/queue")
    async def get_queue(request: Request):
        return await request.app.state.queue.serialize()

    @router.post("/")
    async def post_alert(request: Request):
        try:
            alert_state = await request.json()
            logger.debug("Alert received", extra={'payload': alert_state})
            await request.app.state.queue.put_first(datetime.now(timezone.utc), 'alert', None, None, alert_state)
            return alert_state
        except Exception as e:
            logger.error("Alert processing error", extra={'error': str(e)})
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/app")
    @router.put("/app")
    async def handle_app_buttons(request: Request):
        try:
            if request.app.state.messenger.type == 'slack':
                form_data = await request.form()
                payload = json.loads(form_data['payload'])
            else:
                payload = await request.json()

            return await request.app.state.messenger.buttons_handler(
                payload,
                request.app.state.incidents,
                request.app.state.queue,
                request.app.state.route
            )
        except Exception as e:
            logger.error("App buttons error", extra={'error': str(e)})
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/incidents")
    async def get_incidents(request: Request):
        return request.app.state.incidents.serialize()

    @router.get("/ui_config")
    async def get_ui_config():
        return get_all_ui_config()

    def _get_assignable_users(messenger):
        if messenger and hasattr(messenger, 'users') and hasattr(messenger.users, 'get_assignable_users'):
            return messenger.users.get_assignable_users()
        return []

    def _get_acting_user(request: Request):
        if not auth_manager:
            return None
        session_id = request.cookies.get(auth_manager.session_cookie_name)
        auth_result = auth_manager.get_current_user(session_id=session_id)
        if not auth_result.get("authenticated"):
            raise HTTPException(status_code=401, detail=_MSG_AUTHENTICATION_REQUIRED)
        return auth_result.get("user", {})

    def _get_acting_user_from_websocket(websocket: WebSocket):
        if not auth_manager:
            return None
        session_id = websocket.cookies.get(auth_manager.session_cookie_name)
        auth_result = auth_manager.get_current_user(session_id=session_id)
        if not auth_result.get("authenticated"):
            return None
        return auth_result.get("user", {})

    @router.get("/chains_config", responses={
        401: {"description": _MSG_AUTHENTICATION_REQUIRED},
    })
    async def get_chains_config(request: Request):
        config = get_config()
        app = config.app
        runtime_messenger = request.app.state.messenger
        configured_messenger = config.messenger
        runtime_chains = runtime_messenger.chains if getattr(runtime_messenger, "chains", None) else {}
        configured_chains = configured_messenger.chains if getattr(configured_messenger, "chains", None) else {}
        ui_chains = [n for n, c in configured_chains.items() if isinstance(c, dict) and c.get("type") == "ui"]
        assignable_users = _get_assignable_users(runtime_messenger)
        acting_user = _get_acting_user(request)
        return {
            "users": [user["config_name"] for user in assignable_users if user.get("config_name")],
            "user_groups": list(runtime_messenger.user_groups.keys()) if getattr(runtime_messenger, "user_groups", None) else [],
            "groups": list(runtime_messenger.groups.keys()) if getattr(runtime_messenger, "groups", None) else [],
            "chains": list(runtime_chains.keys()),
            "webhooks": list(app.webhooks.keys()) if getattr(app, "webhooks", None) else [],
            "week_start": app.general.week_start if app.general else "Mon",
            "timezone": app.general.timezone if app.general else "UTC",
            "messenger_type": runtime_messenger.type.value,
            "user_timezone": (acting_user or {}).get("timezone"),
            "ui_chains": ui_chains,
        }

    @router.get("/assignment_users")
    async def get_assignment_users(request: Request):
        return _get_assignable_users(request.app.state.messenger)

    def _log_ui_action(action_name, incident, acting_user, **extra):
        acting_name = (acting_user or {}).get("full_name") or (acting_user or {}).get("username") or "unknown"
        acting_id = (acting_user or {}).get("id") or "unknown"
        log_extra = {"uuid": incident.uuid, "acting_user": acting_name, "acting_user_id": acting_id}
        log_extra.update(extra)
        logger.info(f"UI {action_name}", extra=log_extra)

    @router.post("/assign", responses={
        400: {"description": "Missing uniq_id or user_id"},
        401: {"description": _MSG_AUTHENTICATION_REQUIRED},
        404: {"description": _MSG_INCIDENT_NOT_FOUND},
    })
    async def post_assign(request: Request):
        acting_user = _get_acting_user(request)

        body = await request.json()
        uniq_id = body.get("uniq_id")
        user_id = body.get("user_id")
        if not uniq_id:
            raise HTTPException(status_code=400, detail="uniq_id is required")
        if user_id is None:
            raise HTTPException(status_code=400, detail="user_id is required")

        incident = request.app.state.incidents.get_by_uniq_id(uniq_id)
        if incident is None:
            raise HTTPException(status_code=404, detail=_MSG_INCIDENT_NOT_FOUND)

        messenger = request.app.state.messenger
        queue = request.app.state.queue
        if user_id == "":
            _log_ui_action("unassignment", incident, acting_user)
            unassigned = await messenger.handle_ui_unassign(incident, queue)
            return {"success": unassigned}

        _log_ui_action("assignment", incident, acting_user, target_user_id=user_id)

        assigned = await messenger.handle_ui_assignment(incident, user_id, queue)
        return {"success": assigned}

    @router.post("/task", responses={
        400: {"description": _MSG_UNIQ_ID_REQUIRED},
        401: {"description": _MSG_AUTHENTICATION_REQUIRED},
        404: {"description": _MSG_INCIDENT_NOT_FOUND},
        409: {"description": "Task already exists or creation in progress"},
    })
    async def post_task(request: Request):
        acting_user = _get_acting_user(request)

        body = await request.json()
        uniq_id = body.get("uniq_id")
        if not uniq_id:
            raise HTTPException(status_code=400, detail=_MSG_UNIQ_ID_REQUIRED)

        incident = request.app.state.incidents.get_by_uniq_id(uniq_id)
        if incident is None:
            raise HTTPException(status_code=404, detail=_MSG_INCIDENT_NOT_FOUND)

        if incident.task_link or incident.task_creation_in_progress:
            raise HTTPException(status_code=409, detail="Task already exists or creation in progress")

        _log_ui_action("task", incident, acting_user)

        messenger = request.app.state.messenger
        queue = request.app.state.queue
        result = await messenger.handle_task_button(incident, queue)
        return {"success": True, "result": result}

    @router.post("/freeze", responses={
        400: {"description": "Missing uniq_id or freeze_option"},
        401: {"description": _MSG_AUTHENTICATION_REQUIRED},
        404: {"description": _MSG_INCIDENT_NOT_FOUND},
        409: {"description": "Incident already frozen"},
    })
    async def post_freeze(request: Request):
        acting_user = _get_acting_user(request)

        body = await request.json()
        uniq_id = body.get("uniq_id")
        freeze_option = body.get("freeze_option")
        if not uniq_id or not freeze_option:
            raise HTTPException(status_code=400, detail="uniq_id and freeze_option are required")

        valid_options = ("tomorrow", "next_monday", "month", "6months")
        if freeze_option not in valid_options:
            raise HTTPException(status_code=400, detail=f"freeze_option must be one of {valid_options}")

        incident = request.app.state.incidents.get_by_uniq_id(uniq_id)
        if incident is None:
            raise HTTPException(status_code=404, detail=_MSG_INCIDENT_NOT_FOUND)

        if incident.is_frozen():
            raise HTTPException(status_code=409, detail="Incident is already frozen")

        user_tz = (acting_user or {}).get("timezone")
        _log_ui_action("freeze", incident, acting_user, freeze_option=freeze_option)

        messenger = request.app.state.messenger
        queue = request.app.state.queue
        incidents = request.app.state.incidents
        await messenger.handle_ui_freeze(incident, freeze_option, str((acting_user or {}).get("id", "")), incidents, queue, user_timezone=user_tz)
        return {"success": True}

    @router.post("/unfreeze", responses={
        400: {"description": _MSG_UNIQ_ID_REQUIRED},
        401: {"description": _MSG_AUTHENTICATION_REQUIRED},
        404: {"description": _MSG_INCIDENT_NOT_FOUND},
        409: {"description": "Incident not manually frozen"},
    })
    async def post_unfreeze(request: Request):
        acting_user = _get_acting_user(request)

        body = await request.json()
        uniq_id = body.get("uniq_id")
        if not uniq_id:
            raise HTTPException(status_code=400, detail=_MSG_UNIQ_ID_REQUIRED)

        incident = request.app.state.incidents.get_by_uniq_id(uniq_id)
        if incident is None:
            raise HTTPException(status_code=404, detail=_MSG_INCIDENT_NOT_FOUND)

        if not incident.can_manual_unfreeze():
            raise HTTPException(status_code=409, detail="Cannot unfreeze: not a manual freeze")

        _log_ui_action("unfreeze", incident, acting_user)

        messenger = request.app.state.messenger
        queue = request.app.state.queue
        await messenger.handle_ui_unfreeze(incident, queue)
        return {"success": True}

    @router.post("/release", responses={
        400: {"description": _MSG_UNIQ_ID_REQUIRED},
        401: {"description": _MSG_AUTHENTICATION_REQUIRED},
        404: {"description": _MSG_INCIDENT_NOT_FOUND},
        409: {"description": "Incident not eligible for release"},
    })
    async def post_release(request: Request):
        acting_user = _get_acting_user(request)

        body = await request.json()
        uniq_id = body.get("uniq_id")
        if not uniq_id:
            raise HTTPException(status_code=400, detail=_MSG_UNIQ_ID_REQUIRED)

        incident = request.app.state.incidents.get_by_uniq_id(uniq_id)
        if incident is None:
            raise HTTPException(status_code=404, detail=_MSG_INCIDENT_NOT_FOUND)

        if incident.status != "resolved" or not incident.assigned_user_id:
            raise HTTPException(status_code=409, detail="Incident must be resolved and assigned to release")

        _log_ui_action("release", incident, acting_user)

        messenger = request.app.state.messenger
        await messenger.handle_ui_release(incident)
        return {"success": True}

    @router.post("/-/reload")
    async def post_reload(request: Request):
        if is_standby_mode(request.app.state):
            raise HTTPException(status_code=503, detail=STANDBY_MODE_MESSAGE)
        
        try:
            from app.lifespan import create_main_objects, _cleanup_application_objects
            
            logger.info("Reloading configuration via API")
            success = reload_config()
            if success:
                await _cleanup_application_objects(request.app, reload=True)
                await create_main_objects(request.app, reload=True)
                logger.info("Configuration reloaded via API")
                return Response(
                    status_code=200,
                    content="OK",
                    media_type="text/plain"
                )
            else:
                raise HTTPException(status_code=400, detail="Configuration reload failed")
        except Exception as e:
            logger.error("Configuration reload error via API", extra={'error': str(e)})
            raise HTTPException(status_code=500, detail=str(e))

    @router.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        if is_standby_mode(websocket.app.state):
            await websocket.close(code=1008, reason=STANDBY_MODE_MESSAGE)
            return
        
        await incident_ws.connect(websocket)

        active_maintenance = websocket.app.state.maintenance_manager.active_windows_payload()
        await websocket.send_text(json.dumps({"event": "active_maintenance", "data": active_maintenance}))

        try:
            while True:
                data = await websocket.receive_text()

                try:
                    message = json.loads(data)
                    event_type = message.get("event")

                    if event_type == "request_data":
                        show_full_table = message.get("show_full_table", False)
                        await incident_ws.handle_request_data(websocket, websocket.app.state.incidents, show_full_table)
                    elif event_type == "ping":
                        await incident_ws.handle_ping(websocket)
                    elif event_type == "request_ui_chains":
                        if auth_manager and _get_acting_user_from_websocket(websocket) is None:
                            await websocket.send_text(json.dumps({
                                "event": "ui_chains_error",
                                "detail": _MSG_AUTHENTICATION_REQUIRED,
                            }))
                        else:
                            chain_name = message.get("chain_name", "")
                            ui_chains_store.prune_expired_shifts(chain_name)
                            shifts = ui_chains_store.load_shifts(chain_name)
                            await websocket.send_text(json.dumps({"event": "ui_chains_data", "data": shifts}))
                    elif event_type == "save_ui_chains":
                        if auth_manager and _get_acting_user_from_websocket(websocket) is None:
                            await websocket.send_text(json.dumps({
                                "event": "ui_chains_saved",
                                "success": False,
                                "detail": _MSG_AUTHENTICATION_REQUIRED,
                            }))
                        else:
                            chain_name = message.get("chain_name", "")
                            shifts = message.get("data", [])
                            success = ui_chains_store.save_shifts(chain_name, shifts)
                            await websocket.send_text(json.dumps({"event": "ui_chains_saved", "success": success}))
                    elif event_type == "request_maintenance":
                        if auth_manager and _get_acting_user_from_websocket(websocket) is None:
                            await websocket.send_text(json.dumps({
                                "event": "maintenance_error",
                                "detail": _MSG_AUTHENTICATION_REQUIRED,
                            }))
                        else:
                            store = get_maintenance_store()
                            store.prune_expired_windows()
                            windows = store.load_windows()
                            await websocket.send_text(json.dumps({"event": "maintenance_data", "data": windows}))
                    elif event_type == "save_maintenance":
                        if auth_manager and _get_acting_user_from_websocket(websocket) is None:
                            await websocket.send_text(json.dumps({
                                "event": "maintenance_saved",
                                "success": False,
                                "detail": _MSG_AUTHENTICATION_REQUIRED,
                            }))
                        else:
                            windows_payload = message.get("data", [])
                            store = get_maintenance_store()
                            existing = store.load_windows()
                            existing_by_id = {w["id"]: w for w in existing}
                            assignable_user_ids = {
                                str(user["user_id"])
                                for user in _get_assignable_users(websocket.app.state.messenger)
                            }
                            try:
                                windows = windows_from_ws_payload(
                                    windows_payload,
                                    assignable_user_ids,
                                    existing_by_id,
                                )
                            except HTTPException as exc:
                                await websocket.send_text(json.dumps({
                                    "event": "maintenance_saved",
                                    "success": False,
                                    "detail": exc.detail,
                                }))
                            else:
                                deleted = removed_windows(existing, windows)
                                success = store.save_windows(windows)
                                await websocket.send_text(json.dumps({
                                    "event": "maintenance_saved",
                                    "success": success,
                                }))
                                if success:
                                    _maintenance_save_task = asyncio.create_task(
                                        _maintenance_save_side_effects(
                                            websocket.app, existing, windows, deleted
                                        )
                                    )

                except json.JSONDecodeError:
                    logger.warning("Invalid WebSocket JSON", extra={'data': data})
                except Exception as e:
                    logger.error("WebSocket message error", extra={'error': str(e)})

        except WebSocketDisconnect:
            incident_ws.disconnect(websocket)
        except Exception as e:
            logger.error("WebSocket error", extra={'error': str(e)})
            incident_ws.disconnect(websocket)

    return router
