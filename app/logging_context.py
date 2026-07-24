import re
from contextvars import ContextVar
from dataclasses import dataclass

from app.http_client.errors import classify_messenger_http_error

TELEGRAM_BOT_TOKEN_IN_URL = re.compile(r'(https://api\.telegram\.org/bot)[^/?#]+')


@dataclass(frozen=True)
class MessengerInitContext:
    step: str
    messenger: str


messenger_init_context: ContextVar[MessengerInitContext | None] = ContextVar(
    'messenger_init_context',
    default=None,
)


def redact_messenger_url(url: str) -> str:
    return TELEGRAM_BOT_TOKEN_IN_URL.sub(r'\1***', url)


def exception_fields(exc: BaseException) -> dict[str, str]:
    return {
        'error_type': type(exc).__name__,
        'detail': str(exc) or type(exc).__name__,
    }


def transport_failure_fields(exc: BaseException) -> dict[str, str]:
    failure = classify_messenger_http_error(exc)
    return {
        'failure': failure,
        'detail': str(exc) or failure,
    }


def messenger_init_log_fields() -> dict[str, str]:
    init_ctx = messenger_init_context.get()
    if init_ctx is None:
        return {}
    return {
        'step': init_ctx.step,
        'messenger': init_ctx.messenger,
    }
