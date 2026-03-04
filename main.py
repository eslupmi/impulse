import uvicorn
from fastapi import FastAPI

from app.cli import parse_arguments
from app.config.config import validate_config_only
from app.config.environment import get_environment_config
from app.lifespan import lifespan
from app.logging import configure_logging
from app.middleware import StandbyMiddleware
from app.signals import setup_sighup_forwarder


app = FastAPI(
    title="IMPulse",
    description="Incident Management Platform",
    version="0.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None
)
app.add_middleware(StandbyMiddleware)


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
