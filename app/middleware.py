from fastapi import Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config.config import get_config


def is_standby_mode(state) -> bool:
    """Check if server is in standby mode"""
    return getattr(state, 'is_standby', False)


def service_unavailable_response(message: str) -> Response:
    """Create a 503 Service Unavailable response"""
    return Response(
        status_code=503,
        content=message,
        media_type="text/plain"
    )


class StandbyMiddleware(BaseHTTPMiddleware):
    """Middleware to block all requests except /ready when in standby mode"""
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/"):
            path = "/" + path
        
        # Get http_prefix from config
        config_data = get_config()
        http_prefix = config_data.http_prefix or ""
        
        # Check if path is /ready (with or without prefix)
        # Endpoint is registered directly in app with prefix, so check full path
        if path == f"{http_prefix}/ready":
            return await call_next(request)
        
        # Check if server is in standby mode
        if is_standby_mode(request.app.state):
            # Remove prefix from path for static files check
            if http_prefix and path.startswith(http_prefix):
                path = path[len(http_prefix):]
            if not path.startswith("/"):
                path = "/" + path
            
            # Allow static files
            if path.startswith("/static/"):
                return await call_next(request)
            
            # Block all other requests
            return service_unavailable_response("Service Unavailable - Standby mode. Only /ready endpoint is available.")
        
        return await call_next(request)

