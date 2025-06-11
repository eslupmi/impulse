import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.im.channels import check_channels
from app.im.helpers import get_application
from app.incident.incidents import Incidents
from app.logging import logger, configure_uvicorn_logging
from app.queue.manager import AsyncQueueManager
from app.queue.queue import AsyncQueue
from app.route import generate_route
from app.ui.table_config import get_all_ui_config
from app.ui.websocket import incident_ws
from app.webhook import generate_webhooks
from config import settings, check_updates, application, ui_config

@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """Manage application lifecycle"""
    # Initialize components
    route_dict = settings.get('route')
    webhooks_dict = settings.get('webhooks')

    route = generate_route(route_dict)
    channels = check_channels(route.get_uniq_channels(), application['channels'], route.channel)
    messenger = get_application(application, channels, route.channel)
    webhooks = generate_webhooks(webhooks_dict)
    incidents = Incidents.create_or_load(messenger.type, messenger.public_url, messenger.team)
    
    # Create async queue and manager
    queue = await AsyncQueue.recreate_queue(incidents, check_updates)
    queue_manager = AsyncQueueManager(queue, messenger, incidents, webhooks, route)
    
    # Attach to app state
    fastapi_app.state.queue = queue
    fastapi_app.state.queue_manager = queue_manager
    fastapi_app.state.incidents = incidents
    fastapi_app.state.messenger = messenger
    fastapi_app.state.webhooks = webhooks
    fastapi_app.state.route = route
    
    # Start background queue processing
    await queue_manager.start_processing()
    
    # Start periodic update check
    asyncio.create_task(periodic_update_check(fastapi_app))
    
    logger.info('IMPulse started!')
    
    yield
    
    if fastapi_app.state.queue_manager:
        await fastapi_app.state.queue_manager.stop_processing()
    
    # Cleanup chains
    if hasattr(fastapi_app.state.messenger, 'chains'):
        for chain in fastapi_app.state.messenger.chains.values():
            if hasattr(chain, 'cleanup'):
                chain.cleanup()
    
    logger.info('IMPulse shutdown complete')


async def periodic_update_check(app: FastAPI):
    """Periodic task to check for updates (replaces APScheduler)"""
    while True:
        try:
            await asyncio.sleep(24 * 60 * 60)  # 24 hours
            await app.state.queue.put(datetime.utcnow(), 'check_update', None, None)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in periodic update check: {e}")

app = FastAPI(
    title="IMPulse",
    description="Incident Management Platform",
    version="0.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None
)

if ui_config:
    app.mount("/static", StaticFiles(directory="static"), name="static")
    templates = Jinja2Templates(directory="templates")

    @app.get("/", response_class=HTMLResponse)
    async def get_index(request: Request):
        """Serve the main page"""
        return templates.TemplateResponse("index.html", {"request": request})

@app.get("/queue")
async def get_queue(request: Request):
    """Get current queue state"""
    return await request.app.state.queue.serialize()


@app.post("/")
async def post_alert(request: Request):
    """Handle incoming alerts"""
    try:
        alert_state = await request.json()
        await request.app.state.queue.put_first(datetime.utcnow(), 'alert', None, None, alert_state)
        return alert_state
    except Exception as e:
        logger.error(f"Error processing alert: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/app")
@app.put("/app")
async def handle_app_buttons(request: Request):
    """Handle application button interactions"""
    try:
        if request.app.state.messenger.type == 'slack':
            form_data = await request.form()
            payload = json.loads(form_data['payload'])
        else:
            payload = await request.json()
        
        # Note: This needs to be made async in the messenger implementation
        return request.app.state.messenger.buttons_handler(
            payload, 
            request.app.state.incidents, 
            request.app.state.queue, 
            request.app.state.route
        )
    except Exception as e:
        logger.error(f"Error handling app buttons: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/incidents")
async def get_incidents(request: Request):
    """Get all incidents"""
    return request.app.state.incidents.serialize()


@app.get("/ui_config")
async def get_ui_config():
    """Get complete UI configuration"""
    return get_all_ui_config()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections"""
    await incident_ws.connect(websocket)
    
    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                if message.get("event") == "request_data":
                    await incident_ws.handle_request_data(websocket, websocket.app.state.incidents)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received from WebSocket: {data}")
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")
                
    except WebSocketDisconnect:
        await incident_ws.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await incident_ws.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    
    configure_uvicorn_logging()
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=5000,
        reload=True,
        log_level="warning"
    )
