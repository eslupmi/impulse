from base64 import b64encode
from typing import Mapping, Optional, Sequence
from urllib.parse import urlencode

import aiohttp
import jwt

from app.ui.authentication.models.auth_user import AuthUser
from app.ui.authentication.providers.base_provider import AuthenticationProvider, AuthenticationProviderError


class TelegramAuthenticationProvider(AuthenticationProvider):
    name = "telegram"

    ISSUER = "https://oauth.telegram.org"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        scopes: Sequence[str] = ("openid", "profile"),
        authorize_url: str = "https://oauth.telegram.org/auth",
        token_url: str = "https://oauth.telegram.org/token",
        jwks_url: str = "https://oauth.telegram.org/.well-known/jwks.json",
        timeout_seconds: float = 10.0,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.scopes = tuple(scopes)
        self.authorize_url = authorize_url
        self.token_url = token_url
        self.jwks_url = jwks_url
        self.timeout_seconds = timeout_seconds
        self._jwks_cache: Optional[dict] = None

    def build_authorization_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": " ".join(self.scopes),
        }
        return f"{self.authorize_url}?{urlencode(params)}"

    async def _exchange_code(self, code: str, redirect_uri: str) -> dict:
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.client_id,
        }
        credentials = b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        headers = {"Authorization": f"Basic {credentials}"}

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(self.token_url, data=payload, headers=headers) as response:
                data = await response.json(content_type=None)
                if response.status != 200:
                    raise AuthenticationProviderError(
                        "auth_failed", f"Telegram token exchange failed with status {response.status}"
                    )
                if not data.get("id_token"):
                    raise AuthenticationProviderError("auth_failed", "Telegram id_token not found in response")
                return data

    async def _fetch_jwks(self) -> dict:
        if self._jwks_cache is not None:
            return self._jwks_cache

        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(self.jwks_url) as response:
                if response.status != 200:
                    raise AuthenticationProviderError("auth_failed", "Failed to fetch Telegram JWKS")
                data = await response.json(content_type=None)
                self._jwks_cache = data
                return data

    async def _decode_id_token(self, id_token: str) -> dict:
        try:
            header = jwt.get_unverified_header(id_token)
        except jwt.DecodeError as exc:
            raise AuthenticationProviderError("auth_failed", "Invalid id_token format") from exc

        kid = header.get("kid")
        signing_key = await self._find_signing_key(kid)

        if signing_key is None:
            self._jwks_cache = None
            signing_key = await self._find_signing_key(kid)

        if signing_key is None:
            raise AuthenticationProviderError("auth_failed", "No matching key in Telegram JWKS")

        try:
            return jwt.decode(
                id_token,
                signing_key,
                algorithms=["RS256", "ES256"],
                audience=self.client_id,
                issuer=self.ISSUER,
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationProviderError("auth_failed", f"id_token validation failed: {exc}") from exc

    async def _find_signing_key(self, kid: Optional[str]):
        jwks_data = await self._fetch_jwks()
        for key_data in jwks_data.get("keys", []):
            if kid is None or key_data.get("kid") == kid:
                return jwt.PyJWK(key_data).key
        return None

    async def authenticate_callback(self, params: Mapping[str, str], redirect_uri: str) -> AuthUser:
        error = params.get("error")
        if error:
            raise AuthenticationProviderError("provider_error", error)

        code = params.get("code")
        if not code:
            raise AuthenticationProviderError("missing_code")

        token_data = await self._exchange_code(code, redirect_uri)
        claims = await self._decode_id_token(token_data["id_token"])

        user_id = str(claims.get("id") or claims.get("sub") or "")
        if not user_id:
            raise AuthenticationProviderError("auth_failed", "Telegram user id not found in id_token")

        return AuthUser(
            id=user_id,
            username=claims.get("preferred_username"),
            full_name=claims.get("name"),
            email=None,
            messenger=self.name,
        )
