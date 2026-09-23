"""Core transport and auth-model adapter for public provider authentication."""
from dataclasses import asdict

from app.http_client.rate_limited_client import RateLimitedClient
from app.im.plugin_api import AuthenticationError
from app.ui.authentication.models.auth_user import AuthUser
from app.ui.authentication.providers.base_provider import AuthenticationProvider, AuthenticationProviderError


class RegisteredAuthenticationProvider(AuthenticationProvider):
    def __init__(self, provider):
        self.provider = provider
        self.name = provider.name

    def build_authorization_url(self, state, redirect_uri):
        return self.provider.build_authorization_url(state, redirect_uri)

    async def authenticate_callback(self, params, redirect_uri):
        # Authorization codes are one-shot: no automatic exchange retries.
        http = RateLimitedClient(retry_attempts=1, timeout=10.0)
        http.initialize_client()
        try:
            user = await self.provider.authenticate_callback(params, redirect_uri, http)
            return AuthUser(**asdict(user), messenger=self.name)
        except AuthenticationError as exc:
            raise AuthenticationProviderError(exc.code) from None
        finally:
            await http.close()
