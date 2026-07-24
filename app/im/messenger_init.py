import functools
from contextlib import contextmanager

from app.http_client.errors import MESSENGER_TRANSPORT_ERRORS
from app.logging import logger
from app.logging_context import (
    MessengerInitContext,
    exception_fields,
    messenger_init_context,
    redact_messenger_url,
)


def _log_init_failure(self, step: str, exc: BaseException) -> None:
    logger.error(
        "Messenger initialization failed",
        extra={
            'messenger': self.type.value,
            'url': redact_messenger_url(self.url),
            'step': step,
            **exception_fields(exc),
        },
    )


@contextmanager
def _init_step_context(self, step: str):
    token = messenger_init_context.set(
        MessengerInitContext(step=step, messenger=self.type.value)
    )
    try:
        yield
    except MESSENGER_TRANSPORT_ERRORS:
        raise
    except Exception as exc:
        # Init steps can fail on config, parsing, and API logic — not only transport.
        # Transport errors re-raise without logging here; HTTP client logs those with step context.
        _log_init_failure(self, step, exc)
        raise
    finally:
        messenger_init_context.reset(token)


def messenger_init_step_sync(step: str):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            with _init_step_context(self, step):
                return func(self, *args, **kwargs)

        return wrapper

    return decorator


def messenger_init_step_async(step: str):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            with _init_step_context(self, step):
                return await func(self, *args, **kwargs)

        return wrapper

    return decorator
