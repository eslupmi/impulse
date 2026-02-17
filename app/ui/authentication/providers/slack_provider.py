from typing import Sequence
from urllib.parse import urlencode

import aiohttp

from app.ui.authentication.models.auth_user import AuthUser
from app.ui.authentication.providers.base_provider import AuthenticationProvider


class SlackAuthenticationProvider(AuthenticationProvider):
    name = "slack"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        scopes: Sequence[str] = ("openid", "profile", "email"),
        authorize_url: str = "https://slack.com/oauth/v2/authorize",
        token_url: str = "https://slack.com/api/oauth.v2.access",
        user_url: str = "https://slack.com/api/users.identity",
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
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": " ".join(self.scopes),
        }
        return f"{self.authorize_url}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> str:
        payload = {
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
                    raise ValueError(f"Slack token exchange failed with status {response.status}")
                if data.get("ok") is False:
                    raise ValueError(f"Slack token exchange failed: {data.get('error', 'unknown')}")

                token = data.get("access_token")
                if not token:
                    token = (data.get("authed_user") or {}).get("access_token")
                if not token:
                    raise ValueError("Slack access token not found in response")
                return token

    async def fetch_user(self, access_token: str) -> AuthUser:
        headers = {"Authorization": f"Bearer {access_token}"}
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(self.user_url, headers=headers) as response:
                data = await response.json(content_type=None)
                if response.status != 200:
                    raise ValueError(f"Slack user fetch failed with status {response.status}")
                if data.get("ok") is False:
                    raise ValueError(f"Slack user fetch failed: {data.get('error', 'unknown')}")

                user_data = data.get("user") if isinstance(data.get("user"), dict) else data
                user_id = str(
                    user_data.get("id")
                    or user_data.get("user_id")
                    or data.get("sub")
                    or ""
                )
                if not user_id:
                    raise ValueError("Slack user id not found in response")

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
