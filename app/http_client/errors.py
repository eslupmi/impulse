import asyncio

import aiohttp

MESSENGER_TRANSPORT_ERRORS = (asyncio.TimeoutError, aiohttp.ClientConnectionError)


def classify_messenger_http_error(exc: BaseException) -> str:
    if isinstance(exc, asyncio.TimeoutError):
        return 'timeout'
    if isinstance(exc, aiohttp.ClientConnectionError):
        return 'connection_failed'
    return 'unknown'
