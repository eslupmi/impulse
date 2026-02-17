from abc import ABC, abstractmethod

from app.ui.authentication.models.auth_user import AuthUser


class AuthenticationProvider(ABC):
    name: str = ""

    def is_supported(self) -> bool:
        return True

    @abstractmethod
    def build_authorization_url(self, state: str, redirect_uri: str) -> str:
        pass

    @abstractmethod
    async def exchange_code(self, code: str, redirect_uri: str) -> str:
        pass

    @abstractmethod
    async def fetch_user(self, access_token: str) -> AuthUser:
        pass
