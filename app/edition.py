"""Select the edition once, before application configuration is loaded."""
from app.config.environment import get_environment_config

EDITION = get_environment_config().dev_edition
