from typing import Dict, Optional

from app.config.environment import get_environment_config


def http_proxy_url() -> Optional[str]:
    """Return IMPULSE_PROXY for aiohttp ClientSession(proxy=...)."""
    return get_environment_config().proxy_url


def requests_proxies() -> Optional[Dict[str, str]]:
    """Return proxies dict for requests.Session, or None when unset."""
    proxy = http_proxy_url()
    if proxy is None:
        return None
    return {"http": proxy, "https": proxy}
