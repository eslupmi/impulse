from typing import Sequence
from urllib.parse import urlencode

import aiohttp

from app.ui.authentication.models.auth_user import AuthUser
from app.ui.authentication.providers.base_provider import AuthenticationProvider


class MattermostAuthenticationProvider(AuthenticationProvider):
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
        self.client_id = client_id
        self.client_secret = client_secret
        self.scopes = tuple(scopes)
        self.authorize_url = authorize_url or f"{base_url}/oauth/authorize"
        self.token_url = token_url or f"{base_url}/oauth/access_token"
        self.user_url = user_url or f"{base_url}/api/v4/users/me"
        self.timeout_seconds = timeout_seconds

    def build_authorization_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(self.scopes),
            "state": state,
        }
        return f"{self.authorize_url}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> str:
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
                    raise ValueError(f"Mattermost token exchange failed with status {response.status}")

                token = data.get("access_token")
                if not token:
                    raise ValueError("Mattermost access token not found in response")
                return token

    async def fetch_user(self, access_token: str) -> AuthUser:
        headers = {"Authorization": f"Bearer {access_token}"}
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(self.user_url, headers=headers) as response:
                data = await response.json(content_type=None)
                if response.status != 200:
                    raise ValueError(f"Mattermost user fetch failed with status {response.status}")

                user_id = str(data.get("id") or "")
                if not user_id:
                    raise ValueError("Mattermost user id not found in response")

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
