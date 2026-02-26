from typing import TYPE_CHECKING

from app.config.validation import MessengerType
from app.logging import logger
from app.ui.authentication.manager import UserAuthenticationManager
from app.ui.authentication.providers.mattermost_provider import MattermostAuthenticationProvider
from app.ui.authentication.providers.slack_provider import SlackAuthenticationProvider
from app.ui.authentication.providers.telegram_provider import TelegramAuthenticationProvider
from app.ui.authentication.providers.unsupported_provider import UnsupportedAuthenticationProvider

if TYPE_CHECKING:
    from app.config.validation import ImpulseConfig
    from app.config.environment import EnvironmentConfig

def build_auth_redirect_uri(config: 'ImpulseConfig', http_prefix: str = "") -> str:
    callback_path = f"{http_prefix}/auth/callback" if http_prefix else "/auth/callback"
    impulse_address = getattr(config.messenger, "impulse_address", None)
    if impulse_address:
        return f"{impulse_address.rstrip('/')}{callback_path}"
    return callback_path


def build_auth_manager(config: 'ImpulseConfig', env_config: 'EnvironmentConfig', http_prefix: str = "") -> UserAuthenticationManager:
    messenger_type = config.messenger.type
    client_id = env_config.auth_client_id.strip()
    client_secret = env_config.auth_client_secret.strip()
    allowed_user_ids = None

    if env_config.auth_whitelist_enabled:
        users = getattr(config.messenger, "users", {}) or {}
        allowed_user_ids = {str(user.id) for user in users.values() if hasattr(user, "id")}
        logger.info(
            "Auth whitelist enabled",
            extra={"allowed_users_count": len(allowed_user_ids), "messenger_type": messenger_type.value},
        )

    provider = UnsupportedAuthenticationProvider()

    if messenger_type == MessengerType.SLACK:
        if client_id and client_secret:
            provider = SlackAuthenticationProvider(client_id=client_id, client_secret=client_secret)
        else:
            logger.warning("Auth disabled for Slack: AUTH_CLIENT_ID and AUTH_CLIENT_SECRET are required")
    elif messenger_type == MessengerType.MATTERMOST:
        mattermost_url = getattr(config.messenger, "address", "").strip()
        if client_id and client_secret and mattermost_url:
            provider = MattermostAuthenticationProvider(
                base_url=mattermost_url,
                client_id=client_id,
                client_secret=client_secret,
            )
        else:
            logger.warning(
                "Auth disabled for Mattermost: AUTH_CLIENT_ID, AUTH_CLIENT_SECRET and messenger.address are required"
            )
    elif messenger_type == MessengerType.TELEGRAM:
        bot_token = env_config.telegram_bot_token.strip()
        widget_path = f"{http_prefix}/auth/telegram/widget" if http_prefix else "/auth/telegram/widget"

        if bot_token:
            provider = TelegramAuthenticationProvider(
                bot_token=bot_token,
                widget_path=widget_path,
                max_auth_age_seconds=300,
                api_base_url=(getattr(config.messenger, "address", None) or "https://api.telegram.org"),
            )
        else:
            logger.warning("Auth disabled for Telegram: TELEGRAM_BOT_TOKEN is required")

    return UserAuthenticationManager(
        provider=provider,
        redirect_uri=build_auth_redirect_uri(config=config, http_prefix=http_prefix),
        cookie_secure=env_config.auth_cookie_secure,
        allowed_user_ids=allowed_user_ids,
    )
