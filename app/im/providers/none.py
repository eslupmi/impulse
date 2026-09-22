"""Always available UI-only provider, with no transport or resource needs."""

import uuid

from app.im.plugin_api import DeliveryResult, MessageRef, ProviderDescriptor, ProviderIdentity, UserProfile


class NoneProvider:
    descriptor = ProviderDescriptor('none', messaging_enabled=False)
    url = ''
    team = None

    def __init__(self, config):
        pass

    async def initialize(self, context):
        return ProviderIdentity(public_url='')

    async def start(self):
        pass

    async def fetch_user(self, user_id):
        return UserProfile(id=user_id, exists=False)

    async def fetch_groups(self):
        return ()

    async def create_incident(self, message):
        return MessageRef(message.channel_id, str(uuid.uuid4()))

    async def update_incident(self, message):
        pass

    async def post_notification(self, message, content):
        return DeliveryResult(200)

    def user_url(self, user, identity):
        return None
