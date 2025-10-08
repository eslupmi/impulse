import argparse
import json
import signal
import sys
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, APIRouter
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config.config import get_config, reload_config
from app.config.validation import MessengerType
from app.im.channel_manager import ChannelManager
from app.im.helpers import get_application
from app.incident.incidents import Incidents
from app.logging import logger, configure_uvicorn_logging
from app.queue.manager import AsyncQueueManager
from app.queue.queue import AsyncQueue
from app.route import generate_route
from app.ui.table_config import get_all_ui_config
from app.ui.websocket import incident_ws
from app.webhook import generate_webhooks


def setup_sighup_handler():
    """Setup only SIGHUP signal handler for configuration reloading, preserving other Uvicorn handlers"""

    def handle_sighup(signum, frame):
        """Handle SIGHUP signal to reload configuration"""
        try:
            logger.info("Received SIGHUP signal, reloading configuration...")
            success = reload_config()
            if success:
                logger.info("Configuration reload completed successfully")
        except Exception as e:
            logger.error(f"Error in SIGHUP signal handler: {e}")
            logger.warning(
                "Configuration reload aborted due to unexpected error, continuing with current configuration")

    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, handle_sighup)
        logger.debug("SIGHUP signal handler registered for configuration reloading (overriding Uvicorn)")
    else:
        logger.warning("SIGHUP signal not available on this platform")


def validate_config_only():
    """Validate configuration and exit"""
    try:
        config = get_config()
        logger.info("Configuration validation successful!\n"
                    f"Application type: {config.messenger.type.value}\n"
                    f"Channels configured: {len(config.messenger.channels)}\n"
                    f"Users configured: {len(config.messenger.users)}")
        if config.app.incident:
            logger.info(f"Incident config: Success")
        if config.app.ui:
            logger.info(f"UI config: Success")
        if config.app.route:
            logger.info(f"Route config: Success")
        sys.exit(0)
    except SystemExit as e:
        if e.code != 0:
            logger.error("Configuration validation failed!")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        sys.exit(1)


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """Manage application lifecycle"""
    config = get_config()
    route_config = config.app.route
    webhooks_config = config.app.webhooks

    route = generate_route(route_config)

    channel_manager = ChannelManager()
    if (config.messenger.type == MessengerType.NONE and
            (not config.messenger.channels or 'default' not in config.messenger.channels)):
        config.messenger.channels = {'default': {'id': 'default'}}
    channels = channel_manager.initialize(route.get_uniq_channels(), config.messenger.channels, route.channel)
    default_channel = route.channel

    messenger = get_application(config.messenger, channels, default_channel)
    await messenger.initialize_async()
    webhooks = generate_webhooks(webhooks_config)
    incidents = Incidents.create_or_load(messenger.type, messenger.public_url, messenger.team)

    queue = await AsyncQueue.recreate_queue(incidents)
    queue_manager = AsyncQueueManager(queue, messenger, incidents, webhooks, route)

    fastapi_app.state.queue = queue
    fastapi_app.state.queue_manager = queue_manager
    fastapi_app.state.incidents = incidents
    fastapi_app.state.messenger = messenger
    fastapi_app.state.webhooks = webhooks
    fastapi_app.state.route = route
    fastapi_app.state.channel_manager = channel_manager
    fastapi_app.state.config = config

    await queue_manager.start_processing()

    logger.info('IMPulse started!')

    yield

    if fastapi_app.state.queue_manager:
        await fastapi_app.state.queue_manager.stop_processing()

    if hasattr(fastapi_app.state.messenger, 'close'):
        await fastapi_app.state.messenger.close()

    if hasattr(fastapi_app.state.messenger, 'chains'):
        for chain in fastapi_app.state.messenger.chains.values():
            if hasattr(chain, 'cleanup'):
                chain.cleanup()

    logger.info('IMPulse shutdown complete')


# Get HTTP prefix from configuration
config = get_config()
http_prefix = config.http_prefix

app = FastAPI(
    title="IMPulse",
    description="Incident Management Platform",
    version="0.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None
)

# Create router with HTTP prefix if specified
if http_prefix:
    router = APIRouter(prefix=http_prefix)
else:
    router = APIRouter()

# Mount static files with prefix
if get_config().ui_config:
    if http_prefix:
        app.mount(f"{http_prefix}/static", StaticFiles(directory="static"), name="static")
    else:
        app.mount("/static", StaticFiles(directory="static"), name="static")
    templates = Jinja2Templates(directory="templates")


    @router.get("/", response_class=HTMLResponse)
    async def get_index(request: Request):
        """Serve the main page"""
        return templates.TemplateResponse("index.html", {
            "request": request,
            "http_prefix": http_prefix
        })


@router.get("/queue")
async def get_queue(request: Request):
    """Get current queue state"""
    return await request.app.state.queue.serialize()


@router.post("/")
async def post_alert(request: Request):
    """Handle incoming alerts"""
    try:
        alert_state = await request.json()
        logger.debug(f"Got alert. Payload: {alert_state}")
        await request.app.state.queue.put_first(datetime.utcnow(), 'alert', None, None, alert_state)
        return alert_state
    except Exception as e:
        logger.error(f"Error processing alert: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/app")
@router.put("/app")
async def handle_app_buttons(request: Request):
    """Handle application button interactions"""
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
        logger.error(f"Error handling app buttons: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/incidents")
async def get_incidents(request: Request):
    """Get all incidents"""
    return request.app.state.incidents.serialize()


@router.get("/ui_config")
async def get_ui_config():
    """Get complete UI configuration"""
    return get_all_ui_config()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections"""
    await incident_ws.connect(websocket)

    try:
        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                event_type = message.get("event")

                if event_type == "request_data":
                    await incident_ws.handle_request_data(websocket, websocket.app.state.incidents)
                elif event_type == "ping":
                    await incident_ws.handle_ping(websocket)

            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received from WebSocket: {data}")
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")

    except WebSocketDisconnect:
        await incident_ws.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await incident_ws.disconnect(websocket)


# Include router in the app
app.include_router(router)


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="IMPulse - Incident Management Platform")
    parser.add_argument(
        '--check',
        action='store_true',
        help='Validate configuration and exit'
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()

    if args.check:
        validate_config_only()
    else:
        setup_sighup_handler()

        import uvicorn

        configure_uvicorn_logging()

        config = get_config()
        
        uvicorn.run(
            "main:app",
            host=config.listen_host,
            port=config.listen_port,
            reload=True,
            log_level="warning"
        )
