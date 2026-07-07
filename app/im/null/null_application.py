import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Dict, Optional

from fastapi.responses import JSONResponse

from app.im.application import Application
from app.im.users import BaseUser
from app.jinja_template import JinjaTemplate

if TYPE_CHECKING:
    from app.incident.incident import Incident
    from app.queue.queue import AsyncQueue


class NullApplication(Application):
    """
    Null implementation of Application interface that provides no-op implementations
    for all messenger functionality. Allows running the application with UI only.
    """

    def __init__(self, app_config, channels, default_channel):
        super().__init__(app_config, channels, default_channel)

    def generate_template(self):
        """Override template generation to avoid requiring template files"""
        return (
            JinjaTemplate(''),
            JinjaTemplate(''),
            JinjaTemplate('')
        )

    async def get_all_groups(self):
        return {}

    async def initialize_async(self):
        self.public_url = ''

    async def buttons_handler(self, payload, incidents, queue_, route):
        return JSONResponse({}, status_code=200)

    def get_notification_destinations(self):
        return []

    def update_incident_payload(self, incident, body, header, status_icons, tz_str):
        return {}

    async def get_user_details(self, user_details):
        return {}

    def create_user(self, name, user_details):
        return None

    async def create_incident_message(self, incident, body, header, status_icons):
        return str(uuid.uuid4())

    async def post_to_thread(self, channel_id, id_, text):
        return 200

    async def update_incident_message(self, incident):
        return

    async def update(self, incident, incident_status, alert_state, updated_status, chain_enabled, status_enabled,
                     task_link=''):
        return

    async def new_version_notification(self, channel_id, new_tag):
        return

    async def notify(self, incident, notify_type, identifier):
        return 200

    async def close(self):
        return

    ### PRIVATE METHODS ###

    def _initialize_specific_params(self):
        return

    def _markdown_links_to_native_format(self, text):
        return text

    def _get_url(self, app_config):
        return ''

    def _get_public_url(self, app_config):
        return ''

    def _get_team_name(self, app_config):
        return None

    def _build_user_profile_url(self, user_id: str, user: BaseUser) -> Optional[str]:
        return None

    def _get_incident_message_payload(self, incident, body, header, status_icons):
        return {}

    def _post_thread_payload(self, channel_id, id_, text):
        return {}

    async def _update_incident_message(self, id_, payload):
        return

    async def _send_create_incident_message(self, payload):
        return str(uuid.uuid4())

    async def _generate_groups(self, groups_dict: Dict):
        return {}

    async def _handle_freeze_action(self, incident_: 'Incident', freeze_option: str, user_id: str, incidents,
                                    queue_: 'AsyncQueue', user_timezone: Optional[str] = None):
        return

    async def post_unfreeze_notification(self, incident_: 'Incident'):
        return
