from abc import ABC, abstractmethod
from typing import Mapping

from app.ui.authentication.models.auth_user import AuthUser


class AuthenticationProviderError(Exception):
    def __init__(self, code: str, message: str = ""):
        self.code = code
        super().__init__(message or code)


class AuthenticationProvider(ABC):
    name: str = ""

    def is_supported(self) -> bool:
        return True

    @abstractmethod
    def build_authorization_url(self, state: str, redirect_uri: str) -> str:
        pass

    @abstractmethod
    async def authenticate_callback(self, params: Mapping[str, str], redirect_uri: str) -> AuthUser:
        pass
