import hashlib
import hmac
import html
import time
from typing import Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.ui.authentication.models.auth_user import AuthUser
from app.ui.authentication.providers.base_provider import AuthenticationProvider, AuthenticationProviderError


class TelegramAuthenticationProvider(AuthenticationProvider):
    name = "telegram"

    def __init__(
        self,
        bot_username: str,
        bot_token: str,
        widget_path: str = "/auth/telegram/widget",
        max_auth_age_seconds: int = 300,
    ):
        self.bot_username = bot_username
        self.bot_token = bot_token
        self.widget_path = widget_path
        self.max_auth_age_seconds = max_auth_age_seconds

    def is_supported(self) -> bool:
        return bool(self.bot_username and self.bot_token)

    def build_authorization_url(self, state: str, redirect_uri: str) -> str:
        params = {"state": state}
        return f"{self.widget_path}?{urlencode(params)}"

    async def authenticate_callback(self, params: Mapping[str, str], redirect_uri: str) -> AuthUser:
        if params.get("error"):
            raise AuthenticationProviderError("provider_error", params.get("error", "provider_error"))

        required = ("id", "auth_date", "hash")
        if any(not params.get(field) for field in required):
            raise AuthenticationProviderError("telegram_missing_fields")

        auth_date_str = params.get("auth_date", "")
        try:
            auth_date = int(auth_date_str)
        except ValueError as exc:
            raise AuthenticationProviderError("telegram_missing_fields") from exc

        now = int(time.time())
        if abs(now - auth_date) > self.max_auth_age_seconds:
            raise AuthenticationProviderError("telegram_auth_expired")

        if not self._is_signature_valid(params):
            raise AuthenticationProviderError("telegram_invalid_signature")

        first_name = (params.get("first_name") or "").strip()
        last_name = (params.get("last_name") or "").strip()
        full_name = f"{first_name} {last_name}".strip() or None

        return AuthUser(
            id=str(params.get("id")),
            username=params.get("username"),
            full_name=full_name,
            email=None,
            messenger=self.name,
        )

    def build_widget_html(self, state: str, redirect_uri: str) -> str:
        auth_url = self._append_state(redirect_uri, state)
        safe_bot_username = html.escape(self.bot_username, quote=True)
        safe_auth_url = html.escape(auth_url, quote=True)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Telegram Login</title>
  <style>
    body {{ font-family: sans-serif; background: #f3f4f6; margin: 0; padding: 24px; }}
    .box {{ max-width: 480px; margin: 60px auto; background: #fff; border-radius: 12px; padding: 24px; text-align: center; box-shadow: 0 8px 24px rgba(0,0,0,0.08); }}
    h1 {{ margin: 0 0 12px; font-size: 20px; }}
    p {{ color: #666; margin: 0 0 20px; }}
  </style>
</head>
<body>
  <div class="box">
    <h1>Login with Telegram</h1>
    <p>Complete authentication to continue.</p>
    <script async src="https://telegram.org/js/telegram-widget.js?22"
            data-telegram-login="{safe_bot_username}"
            data-size="large"
            data-userpic="false"
            data-auth-url="{safe_auth_url}"
            data-request-access="write"></script>
  </div>
</body>
</html>"""

    def _is_signature_valid(self, params: Mapping[str, str]) -> bool:
        received_hash = str(params.get("hash") or "")

        items = []
        for key, value in params.items():
            if key in {"hash", "state", "next", "auth_error"}:
                continue
            if value is None:
                continue
            items.append((key, str(value)))

        items.sort(key=lambda item: item[0])
        data_check_string = "\n".join(f"{key}={value}" for key, value in items)

        secret_key = hashlib.sha256(self.bot_token.encode("utf-8")).digest()
        expected_hash = hmac.new(
            secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected_hash, received_hash)

    @staticmethod
    def _append_state(url: str, state: str) -> str:
        split = urlsplit(url)
        query = dict(parse_qsl(split.query, keep_blank_values=True))
        query["state"] = state
        return urlunsplit((split.scheme, split.netloc, split.path, urlencode(query), split.fragment))
