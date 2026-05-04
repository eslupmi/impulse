from typing import TYPE_CHECKING
from pathlib import Path

from app.config.validation import MessengerType
from app.im.user_store import get_user_store
from app.logging import logger
from app.ui.authentication.manager import UserAuthenticationManager
from app.ui.authentication.models.auth_user import AuthUser
from app.ui.authentication.providers.mattermost_provider import MattermostAuthenticationProvider
from app.ui.authentication.providers.slack_provider import SlackAuthenticationProvider
from app.ui.authentication.providers.telegram_provider import TelegramAuthenticationProvider
from app.ui.authentication.providers.unsupported_provider import UnsupportedAuthenticationProvider
from app.ui.authentication.session_store import FileSessionStore

if TYPE_CHECKING:
    from app.config.validation import ImpulseConfig
    from app.config.environment import EnvironmentConfig

def build_auth_redirect_uri(env_config: 'EnvironmentConfig', http_prefix: str = "") -> str:
    if env_config.auth_redirect_url:
        return env_config.auth_redirect_url
    callback_path = f"{http_prefix}/auth/callback" if http_prefix else "/auth/callback"
    return callback_path


def _build_configured_users(config: 'ImpulseConfig') -> dict[str, AuthUser]:
    users = getattr(config.messenger, "users", {}) or {}
    messenger = config.messenger.type.value
    configured_users: dict[str, AuthUser] = {}
    for user_name, user in users.items():
        user_id = str(getattr(user, "id", "")).strip()
        if not user_id:
            continue
        configured_users[user_id] = AuthUser(
            id=user_id,
            username=getattr(user, "username", None) or user_name,
            full_name=getattr(user, "name", None),
            email=getattr(user, "email", None),
            messenger=messenger,
        )
    return configured_users


def _build_provider(messenger_type: MessengerType, client_id: str, client_secret: str, config: 'ImpulseConfig'):
    if messenger_type == MessengerType.SLACK:
        if client_id and client_secret:
            return SlackAuthenticationProvider(client_id=client_id, client_secret=client_secret)
        logger.warning("Auth disabled for Slack: AUTH_CLIENT_ID and AUTH_CLIENT_SECRET are required")
    elif messenger_type == MessengerType.MATTERMOST:
        mattermost_url = getattr(config.messenger, "address", "").strip()
        if client_id and client_secret and mattermost_url:
            return MattermostAuthenticationProvider(
                base_url=mattermost_url,
                client_id=client_id,
                client_secret=client_secret,
            )
        logger.warning(
            "Auth disabled for Mattermost: AUTH_CLIENT_ID, AUTH_CLIENT_SECRET and messenger.address are required"
        )
    elif messenger_type == MessengerType.TELEGRAM:
        if client_id and client_secret:
            return TelegramAuthenticationProvider(client_id=client_id, client_secret=client_secret)
        logger.warning("Auth disabled for Telegram: AUTH_CLIENT_ID and AUTH_CLIENT_SECRET are required")
    return UnsupportedAuthenticationProvider()


def _build_allowed_user_ids(config: 'ImpulseConfig', messenger_type: MessengerType) -> set[str] | None:
    users = getattr(config.messenger, "users", {}) or {}
    allowed_user_ids = {str(user.id) for user in users.values() if hasattr(user, "id")}
    logger.info(
        "Auth whitelist enabled",
        extra={"allowed_users_count": len(allowed_user_ids), "messenger_type": messenger_type.value},
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
        session_store=FileSessionStore(
            root_dir=str(Path(env_config.data_path) / "sessions"),
            default_cookie_path=http_prefix or "/",
        ),
        user_store=get_user_store(),
    )
