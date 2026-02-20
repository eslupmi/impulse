from typing import Mapping, Sequence
from urllib.parse import urlencode

import aiohttp

from app.ui.authentication.models.auth_user import AuthUser
from app.ui.authentication.providers.base_provider import AuthenticationProvider, AuthenticationProviderError


class SlackAuthenticationProvider(AuthenticationProvider):
    name = "slack"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        scopes: Sequence[str] = ("openid", "profile", "email"),
        authorize_url: str = "https://slack.com/openid/connect/authorize",
        token_url: str = "https://slack.com/api/openid.connect.token",
        user_url: str = "https://slack.com/api/openid.connect.userInfo",
        timeout_seconds: float = 10.0,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.scopes = tuple(scopes)
        self.authorize_url = authorize_url
        self.token_url = token_url
        self.user_url = user_url
        self.timeout_seconds = timeout_seconds

    def build_authorization_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": " ".join(self.scopes),
        }
        return f"{self.authorize_url}?{urlencode(params)}"

    async def _exchange_code(self, code: str, redirect_uri: str) -> str:
        payload = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self.token_url, data=payload) as response:
                data = await response.json(content_type=None)
                if response.status != 200:
                    raise AuthenticationProviderError("auth_failed", f"Slack token exchange failed with status {response.status}")
                if data.get("ok") is False:
                    raise AuthenticationProviderError("auth_failed", f"Slack token exchange failed: {data.get('error', 'unknown')}")

                token = data.get("access_token")
                if not token:
                    raise AuthenticationProviderError("auth_failed", "Slack access token not found in response")
                return token

    async def _fetch_user(self, access_token: str) -> AuthUser:
        headers = {"Authorization": f"Bearer {access_token}"}
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(self.user_url, headers=headers) as response:
                data = await response.json(content_type=None)
                if response.status != 200:
                    raise AuthenticationProviderError("auth_failed", f"Slack user fetch failed with status {response.status}")
                if data.get("ok") is False:
                    raise AuthenticationProviderError("auth_failed", f"Slack user fetch failed: {data.get('error', 'unknown')}")

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

    async def authenticate_callback(self, params: Mapping[str, str], redirect_uri: str) -> AuthUser:
        error = params.get("error")
        if error:
            raise AuthenticationProviderError("provider_error", error)

        code = params.get("code")
        if not code:
            raise AuthenticationProviderError("missing_code")

        access_token = await self._exchange_code(code, redirect_uri)
        return await self._fetch_user(access_token)
