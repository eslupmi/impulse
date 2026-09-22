"""Core-owned compatibility boundary for Phase 1 callbacks and user models.

Legacy callbacks still operate on incidents and queues here, outside the public
provider contract. Their per-platform guards, action order and acknowledgements
are intentionally preserved until each provider's vertical-slice migration.
"""


class LegacyInteractionService:
    def __init__(self, application, legacy_type):
        self.application = application
        self.legacy_type = legacy_type

    _METHODS = frozenset({
        'buttons_handler', 'create_user', 'create_group', 'get_notification_destinations',
        '_generate_groups', '_init_webhook', '_build_button_response', '_dispatch_button_action',
        '_handle_chain_action', '_handle_freeze_button', '_handle_freeze_actions', '_show_freeze_menu',
    })

    def __getattr__(self, name):
        # Only methods defined on the legacy adapter are bound here. Inherited
        # provider methods go through the facade; no second Application exists.
        method = self.legacy_type.__dict__.get(name) if name in self._METHODS else None
        if callable(method):
            return method.__get__(self, type(self))
        return getattr(self.application, name)

    async def handle(self, payload, incidents, queue, route):
        return await self.buttons_handler(payload, incidents, queue, route)

    def update_payload(self, incident, body, header, status_icons, timezone=None, **kwargs):
        from app.im.providers.legacy import LegacyIncidentView
        view = LegacyIncidentView(self.application._presentation(incident, body, header, status_icons, timezone))
        provider = self.application.provider
        if kwargs:
            return provider.update_incident_payload(view, body, header, status_icons, **kwargs)
        return provider.update_incident_payload(view, body, header, status_icons, timezone)

    def create_payload(self, incident, body, header, status_icons):
        from app.im.providers.legacy import LegacyIncidentView
        view = LegacyIncidentView(self.application._presentation(incident, body, header, status_icons))
        return self.application.provider._get_incident_message_payload(view, body, header, status_icons)

    async def get_group_details(self, group_id):
        return await self.application.provider.get_group_details(group_id)

    def markdown_links(self, text):
        return self.application.provider._markdown_links_to_native_format(text)

    def thread_payload(self, channel_id, thread_id, text):
        return self.application.provider._post_thread_payload(channel_id, thread_id, text)

    async def update_payload_message(self, thread_id, payload):
        await self.application.provider._update_incident_message(thread_id, payload)

    async def answer_callback(self, callback_id):
        await self.application.provider._answer_callback(callback_id)
