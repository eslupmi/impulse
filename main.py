import uvicorn
from fastapi import FastAPI

from app.cli import parse_arguments
from app.config.config import get_config, validate_config_only
from app.config.environment import get_environment_config
from app.extensions import load_extensions
from app.lifespan import lifespan
from app.logging import configure_logging
from app.middleware import StandbyMiddleware
from app.routes import create_router
from app.signals import setup_sighup_forwarder
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

auth_manager = build_auth_manager(config=config, env_config=env_config, http_prefix=http_prefix)
router = create_router(http_prefix=http_prefix, fastapi_app=app, auth_manager=auth_manager)
router.include_router(create_auth_router(auth_manager))
app.include_router(router)
load_extensions(app=app, env_config=env_config, config=config, auth_manager=auth_manager)


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
