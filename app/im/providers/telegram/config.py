"""Telegram's public configuration schema."""
from typing import Literal

from pydantic import Field, model_validator

from app.im.plugin_api import BaseApplicationConfig, BaseUser, MessengerType


class TelegramUser(BaseUser):
    id: int = Field(..., description='User ID')
    name: str | None = Field(None, description='User display name')
    username: str | None = Field(None, description='Username')


class TelegramChannel(BaseUser):
    id: int = Field(..., description='Channel ID')
    name: str | None = Field(None, description='Channel name')


class TelegramApplicationConfig(BaseApplicationConfig):
    type: Literal[MessengerType.TELEGRAM] = Field(MessengerType.TELEGRAM, description='Application type')
    channels: dict[str, TelegramChannel] = Field(..., description='Channel definitions')
    users: dict[str, TelegramUser] = Field(..., description='User definitions')

    @model_validator(mode='after')
    def validate_impulse_address_required(self):
        if not self.impulse_address:
            raise ValueError(f'messenger.impulse_address is required for {self.type.value}')
        return self
