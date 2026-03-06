from typing import Sequence

from app.ui.authentication.models.auth_user import AuthUser
from app.ui.authentication.providers.base_provider import AuthenticationProviderError
from app.ui.authentication.providers.oauth_provider import OAuthProvider


class MattermostAuthenticationProvider(OAuthProvider):
    name = "mattermost"

    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        scopes: Sequence[str] = ("openid", "profile", "email"),
        authorize_url: str = None,
        token_url: str = None,
        user_url: str = None,
        timeout_seconds: float = 10.0,
    ):
        base_url = base_url.rstrip("/")
        self.base_url = base_url
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes,
            authorize_url=authorize_url or f"{base_url}/oauth/authorize",
            token_url=token_url or f"{base_url}/oauth/access_token",
            user_url=user_url or f"{base_url}/api/v4/users/me",
            timeout_seconds=timeout_seconds,
        )

    def _parse_user_response(self, data: dict) -> AuthUser:
        user_id = str(data.get("id") or "")
        if not user_id:
            raise AuthenticationProviderError("auth_failed", "Mattermost user id not found in response")

        first_name = (data.get("first_name") or "").strip()
        last_name = (data.get("last_name") or "").strip()
        full_name = f"{first_name} {last_name}".strip() or None

        return AuthUser(
            id=user_id,
            username=data.get("username"),
            full_name=full_name,
            email=data.get("email"),
            messenger=self.name,
        )
