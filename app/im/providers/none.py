"""Always available UI-only provider, with no transport or resource needs."""

import uuid
from typing import Any, Literal

from pydantic import Field, field_validator

from impulse_messenger_api import BaseApplicationConfig, DeliveryResult, MessageRef, MessengerProvider, ProviderDescriptor, ProviderIdentity, UserProfile


class NullApplicationConfig(BaseApplicationConfig):
    """Null messenger configuration for UI-only mode"""
    type: Literal['none'] = Field('none', description="Application type")
    channels: dict[str, Any] = Field(default_factory=dict, description="Channel definitions (not used)")
    users: dict[str, Any] = Field(default_factory=dict, description="User definitions (not used)")
    admin_users: list[str] = Field(default_factory=list, description="Admin users (not used)")
    impulse_address: str | None = Field(None, description="Impulse callback address (not used)")

    @field_validator('admin_users')
    @classmethod
    def validate_admin_users_exist(cls, v, info):
        return v

    @field_validator('chains')
    @classmethod
    def validate_chains_structure_and_references(cls, v, info):
        return v


class NoneProvider(MessengerProvider):
    descriptor = ProviderDescriptor('none', messaging_enabled=False)
    config_model = NullApplicationConfig
    url = ''
    team = None

    def __init__(self, config, secrets=None):
        # UI-only mode accepts the factory arguments but needs no provider state.
        pass

    async def initialize(self, context):
        return ProviderIdentity(public_url='')

    async def activate(self):
        # UI-only mode has no external callbacks to activate.
        pass

    async def fetch_user(self, user_id):
        return UserProfile(id=user_id, exists=False)

    async def fetch_groups(self):
        return ()

    async def create_incident(self, message):
        return MessageRef(message.channel_id, str(uuid.uuid4()))

    async def update_incident(self, message):
        # UI-only mode has no remote message to update.
        pass

    async def post_notification(self, message, content):
        return DeliveryResult(200)

    def user_url(self, user, identity):
        return None
