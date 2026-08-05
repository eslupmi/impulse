from aiohttp import ClientSession


def create_client_session(**kwargs) -> ClientSession:
    """Create ClientSession that honors HTTP_PROXY, HTTPS_PROXY, and NO_PROXY."""
    kwargs.setdefault("trust_env", True)
    return ClientSession(**kwargs)
