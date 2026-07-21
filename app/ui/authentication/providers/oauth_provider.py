from abc import abstractmethod
from typing import Sequence, Mapping
from urllib.parse import urlencode

import aiohttp

from app.http_client.proxy import http_proxy_url
from app.ui.authentication.models.auth_user import AuthUser
from app.ui.authentication.providers.base_provider import AuthenticationProvider, AuthenticationProviderError


class OAuthProvider(AuthenticationProvider):
    """Standard OAuth 2.0 Authorization Code flow shared by Slack, Mattermost, etc."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        scopes: Sequence[str],
        authorize_url: str,
        token_url: str,
        user_url: str,
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
        async with aiohttp.ClientSession(timeout=timeout, proxy=http_proxy_url()) as session:
            async with session.post(self.token_url, data=payload) as response:
                data = await response.json(content_type=None)
                if response.status != 200:
                    raise AuthenticationProviderError(
                        "auth_failed",
                        f"{self.name} token exchange failed with status {response.status}",
                    )
                self._validate_token_response(data)
                token = data.get("access_token")
                if not token:
                    raise AuthenticationProviderError(
                        "auth_failed",
                        f"{self.name} access token not found in response",
                    )
                return token

    def _validate_token_response(self, data: dict) -> None:
        """Override to add provider-specific token response checks."""

    async def _fetch_user(self, access_token: str) -> AuthUser:
        headers = {"Authorization": f"Bearer {access_token}"}
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout, proxy=http_proxy_url()) as session:
            async with session.get(self.user_url, headers=headers) as response:
                data = await response.json(content_type=None)
                if response.status != 200:
                    raise AuthenticationProviderError(
                        "auth_failed",
                        f"{self.name} user fetch failed with status {response.status}",
                    )
                return self._parse_user_response(data)

    @abstractmethod
    def _parse_user_response(self, data: dict) -> AuthUser:
        pass

    async def authenticate_callback(self, params: Mapping[str, str], redirect_uri: str) -> AuthUser:
        error = params.get("error")
        if error:
            raise AuthenticationProviderError("provider_error", error)

        code = params.get("code")
        if not code:
            raise AuthenticationProviderError("missing_code")

        access_token = await self._exchange_code(code, redirect_uri)
        return await self._fetch_user(access_token)
