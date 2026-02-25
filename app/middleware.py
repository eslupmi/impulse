from fastapi import Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config.environment import get_environment_config


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
    """Middleware to block all requests except /readyz, /livez and /metrics when in standby mode"""
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/"):
            path = "/" + path
        
        # Get http_prefix from environment config
        env_config = get_environment_config()
        http_prefix = env_config.http_prefix
        
        # Check if path is /readyz, /livez or /metrics (with or without prefix)
        # Endpoints are registered directly in app with prefix, so check full path
        if path == f"{http_prefix}/readyz" or path == f"{http_prefix}/livez" or path == f"{http_prefix}/metrics":
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
            return service_unavailable_response("Service Unavailable - Standby mode. Only /readyz, /livez and /metrics endpoints are available.")
        
        return await call_next(request)

