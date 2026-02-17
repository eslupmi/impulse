from app.ui.authentication.models.auth_user import AuthUser
from app.ui.authentication.providers.base_provider import AuthenticationProvider


class TelegramAuthenticationProviderMock(AuthenticationProvider):
    name = "telegram"

    def is_supported(self) -> bool:
        return False

    def build_authorization_url(self, state: str, redirect_uri: str) -> str:
        raise NotImplementedError("Telegram authentication is not implemented yet")

    async def exchange_code(self, code: str, redirect_uri: str) -> str:
        raise NotImplementedError("Telegram authentication is not implemented yet")

    async def fetch_user(self, access_token: str) -> AuthUser:
        raise NotImplementedError("Telegram authentication is not implemented yet")
