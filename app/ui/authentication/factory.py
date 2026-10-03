from pathlib import Path
from typing import TYPE_CHECKING

from app.im.user_store import get_user_store
from app.logging import logger
from app.ui.authentication.manager import UserAuthenticationManager
from app.ui.authentication.models.auth_user import AuthUser
from app.im.registry import get_provider_registry
from app.ui.authentication.providers.registered_provider import RegisteredAuthenticationProvider
from app.ui.authentication.providers.unsupported_provider import (
    UnsupportedAuthenticationProvider,
)
from app.ui.authentication.session_store import FileSessionStore

if TYPE_CHECKING:
    from app.config.environment import EnvironmentConfig
    from app.config.validation import ImpulseConfig

def build_auth_redirect_uri(env_config: 'EnvironmentConfig', http_prefix: str = "") -> str:
    if env_config.auth_redirect_url:
        return env_config.auth_redirect_url
    callback_path = f"{http_prefix}/auth/callback" if http_prefix else "/auth/callback"
    return callback_path


def _build_configured_users(config: 'ImpulseConfig') -> dict[str, AuthUser]:
    users = config.messenger.users
    messenger = config.messenger.type
    configured_users: dict[str, AuthUser] = {}
    for user_name, user in users.items():
        user_id = str(user.id).strip()
        if not user_id:
            continue
        configured_users[user_id] = AuthUser(
            id=user_id,
            username=user_name,
            messenger=messenger,
        )
    return configured_users


def _build_provider(messenger_type: str, client_id: str, client_secret: str, config: 'ImpulseConfig'):
    registration = get_provider_registry().resolve(messenger_type)
    if registration.authentication_factory:
        if client_id and client_secret:
            return RegisteredAuthenticationProvider(
                registration.authentication_factory(client_id, client_secret, config.messenger))
        logger.warning('Auth disabled: AUTH_CLIENT_ID and AUTH_CLIENT_SECRET are required',
                       extra={'messenger': messenger_type})
    return UnsupportedAuthenticationProvider()


def _build_allowed_user_ids(config: 'ImpulseConfig', messenger_type: str) -> set[str] | None:
    users = config.messenger.users
    allowed_user_ids = {str(user.id) for user in users.values()}
    logger.info(
        "Auth whitelist enabled",
        extra={"allowed_users_count": len(allowed_user_ids), "messenger_type": messenger_type},
    )
    return allowed_user_ids


def build_auth_manager(config: 'ImpulseConfig', env_config: 'EnvironmentConfig', http_prefix: str = "") -> UserAuthenticationManager:
    messenger_type = config.messenger.type
    client_id = env_config.auth_client_id.strip()
    client_secret = env_config.auth_client_secret.strip()
    configured_users = _build_configured_users(config)
    allowed_user_ids = _build_allowed_user_ids(config, messenger_type) if env_config.auth_whitelist_enabled else None
    provider = _build_provider(messenger_type, client_id, client_secret, config)
    default_redirect_path = http_prefix or "/"

    return UserAuthenticationManager(
        provider=provider,
        redirect_uri=build_auth_redirect_uri(env_config=env_config, http_prefix=http_prefix),
        cookie_secure=env_config.auth_cookie_secure,
        cookie_path=http_prefix or "/",
        allowed_user_ids=allowed_user_ids,
        default_redirect_path=default_redirect_path,
        allowed_redirect_prefixes={default_redirect_path},
        configured_users=configured_users,
        session_store=FileSessionStore(root_dir=str(Path(env_config.data_path) / "sessions")),
        user_store=get_user_store(),
    )
