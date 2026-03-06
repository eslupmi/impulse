from app.ui.authentication.models.auth_user import AuthUser
from app.ui.authentication.providers.base_provider import AuthenticationProviderError
from app.ui.authentication.providers.oauth_provider import OAuthProvider


class SlackAuthenticationProvider(OAuthProvider):
    name = "slack"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        scopes=("openid", "profile", "email"),
        authorize_url="https://slack.com/openid/connect/authorize",
        token_url="https://slack.com/api/openid.connect.token",
        user_url="https://slack.com/api/openid.connect.userInfo",
        timeout_seconds=10.0,
    ):
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes,
            authorize_url=authorize_url,
            token_url=token_url,
            user_url=user_url,
            timeout_seconds=timeout_seconds,
        )

    def _validate_token_response(self, data: dict) -> None:
        if data.get("ok") is False:
            raise AuthenticationProviderError(
                "auth_failed",
                f"Slack token exchange failed: {data.get('error', 'unknown')}",
            )

    def _parse_user_response(self, data: dict) -> AuthUser:
        if data.get("ok") is False:
            raise AuthenticationProviderError(
                "auth_failed",
                f"Slack user fetch failed: {data.get('error', 'unknown')}",
            )

        user_data = data.get("user") if isinstance(data.get("user"), dict) else data
        user_id = str(user_data.get("id") or user_data.get("user_id") or data.get("sub") or "")
        if not user_id:
            raise AuthenticationProviderError("auth_failed", "Slack user id not found in response")

        username = user_data.get("name") or user_data.get("username") or data.get("preferred_username")
        full_name = user_data.get("real_name") or user_data.get("name") or data.get("name")
        email = user_data.get("email") or data.get("email")

        return AuthUser(
            id=user_id,
            username=username,
            full_name=full_name,
            email=email,
            messenger=self.name,
        )
