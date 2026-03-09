from typing import Mapping

from app.ui.authentication.models.auth_user import AuthUser
from app.ui.authentication.providers.base_provider import AuthenticationProvider, AuthenticationProviderError


class UnsupportedAuthenticationProvider(AuthenticationProvider):
    name = "unsupported"

    def __init__(self, reason_code: str = "not_supported"):
        self.reason_code = reason_code

    def is_supported(self) -> bool:
        return False

    def build_authorization_url(self, state: str, redirect_uri: str) -> str:
        raise AuthenticationProviderError(self.reason_code, "Authentication is not supported")

    async def authenticate_callback(self, params: Mapping[str, str], redirect_uri: str) -> AuthUser:
        raise AuthenticationProviderError(self.reason_code, "Authentication is not supported")
