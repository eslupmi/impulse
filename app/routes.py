import json
from datetime import datetime, timezone

from fastapi import APIRouter, FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config.config import get_config, reload_config
from app.logging import logger
from app.metrics import generate_metrics_response
from app.middleware import is_standby_mode, service_unavailable_response, STANDBY_MODE_MESSAGE
from app.ui.table_config import get_all_ui_config
from app.ui.websocket import incident_ws
from app.im.chain.managed_chains_store import managed_chains_store


def create_router(http_prefix: str, fastapi_app: FastAPI = None) -> APIRouter:
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
                    elif event_type == "request_managed_chains":
                        chains = managed_chains_store.load_chains()
                        await websocket.send_text(json.dumps({"event": "managed_chains_data", "data": chains}))
                    elif event_type == "save_managed_chains":
                        chains = message.get("data", [])
                        success = managed_chains_store.save_chains(chains)
                        await websocket.send_text(json.dumps({"event": "managed_chains_saved", "success": success}))

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
