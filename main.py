import json
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, APIRouter
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.cli import parse_arguments
from app.config.config import get_config, validate_config_only
from app.config.environment import get_environment_config
from app.lifespan import lifespan
from app.logging import logger, configure_logging
from app.metrics import STATUS, generate_metrics_response
from app.middleware import StandbyMiddleware, is_standby_mode, service_unavailable_response
from app.signals import setup_sighup_forwarder
from app.ui.table_config import get_all_ui_config
from app.ui.websocket import incident_ws
from app.ui.authentication.factory import build_auth_manager
from app.ui.authentication.router import create_auth_router


app = FastAPI(
    title="IMPulse",
    description="Incident Management Platform",
    version="0.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None
)
app.add_middleware(StandbyMiddleware)

config = get_config()
env_config = get_environment_config()
http_prefix = env_config.http_prefix
router = APIRouter(prefix=http_prefix)


auth_manager = build_auth_manager(
    config=config,
    env_config=env_config,
    http_prefix=http_prefix,
)
router.include_router(create_auth_router(auth_manager))


def get_live(request: Request):
    return Response(status_code=200, content="OK", media_type="text/plain")


def get_ready(request: Request):
    if not hasattr(request.app, 'state'):
        return service_unavailable_response("Service Unavailable - Initializing")

    if is_standby_mode(request.app.state):
        return service_unavailable_response("Service Unavailable - Standby mode")

    if not hasattr(request.app.state, 'queue') or not hasattr(request.app.state, 'queue_manager'):
        return service_unavailable_response("Service Unavailable - Initializing")

    return Response(status_code=200, content="OK", media_type="text/plain")


@router.get("/metrics")
async def get_metrics(request: Request):
    queue = request.app.state.queue
    return await generate_metrics_response(queue)


app.add_api_route(f"{http_prefix}/livez", get_live, methods=["GET"])
app.add_api_route(f"{http_prefix}/readyz", get_ready, methods=["GET"])
app.add_api_route(f"{http_prefix}/metrics", get_metrics, methods=["GET"])

if get_config().ui_config:
    if http_prefix:
        app.mount(f"{http_prefix}/static", StaticFiles(directory="static"), name="static")
    else:
        app.mount("/static", StaticFiles(directory="static"), name="static")
    templates = Jinja2Templates(directory="templates")

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


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    if is_standby_mode(websocket.app.state):
        await websocket.close(code=1008, reason="Service Unavailable - Standby mode")
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

            except json.JSONDecodeError:
                logger.warning("Invalid WebSocket JSON", extra={'data': data})
            except Exception as e:
                logger.error("WebSocket message error", extra={'error': str(e)})

    except WebSocketDisconnect:
        incident_ws.disconnect(websocket)
    except Exception as e:
        logger.error("WebSocket error", extra={'error': str(e)})
        incident_ws.disconnect(websocket)


app.include_router(router)


if __name__ == "__main__":
    args = parse_arguments()
    if args.check:
        validate_config_only()

    setup_sighup_forwarder()

    configure_logging()

    env_config = get_environment_config()
    uvicorn.run(
        "main:app",
        host=env_config.listen_host,
        port=env_config.listen_port,
        log_level="warning"
    )
