import uuid

from fastapi.responses import JSONResponse

from app.im.application import Application


class NullApplication(Application):
    """
    Null implementation of Application interface that provides no-op implementations
    for all messenger functionality. Allows running the application with UI only.
    """

    def __init__(self, app_config, channels, default_channel):
        super().__init__(app_config, channels, default_channel)

    def generate_template(self):
        """Override template generation to avoid requiring template files"""
        from app.im.template import JinjaTemplate
        return (
            JinjaTemplate(''),
            JinjaTemplate(''),
            JinjaTemplate('')
        )

    async def initialize_async(self):
        """No async initialization needed"""
        self.public_url = ''

    async def buttons_handler(self, payload, incidents, queue_, route):
        """No button handling support"""
        return JSONResponse({}, status_code=200)

    def _initialize_specific_params(self):
        """No specific parameters to initialize"""
        pass

    def _markdown_links_to_native_format(self, text):
        """Return text as-is"""
        return text

    def _get_url(self, app_config):
        """No URL needed"""
        return ''

    def _get_public_url(self, app_config):
        """No public URL needed"""
        return ''

    def _get_team_name(self, app_config):
        """No team name needed"""
        return None

    def get_notification_destinations(self):
        """No notification destinations"""
        return []

    def get_admins_text(self):
        """No admins"""
        return ''

    async def send_message(self, channel_id, text, attachment):
        """No message sending"""
        pass

    def _create_thread_payload(self, channel_id, body, header, status_icons, status):
        """Return empty payload"""
        return {}

    def _post_thread_payload(self, channel_id, id_, text):
        """Return empty payload"""
        return {}

    def update_thread_payload(self, channel_id, id_, body, header, status_icons, status, chain_enabled, status_enabled):
        """Return empty payload"""
        return {}

    async def _update_thread(self, id_, payload):
        """No thread updating"""
        pass

    async def get_user_details(self, user_details):
        """No user details"""
        return {}

    def create_user(self, name, user_details):
        """No user creation"""
        return None

    async def create_thread(self, channel_id, body, header, status_icons, status):
        """Generate a synthetic thread ID but don't create actual thread"""
        return str(uuid.uuid4())

    async def _send_create_thread(self, payload):
        """Generate a synthetic thread ID without HTTP call"""
        return str(uuid.uuid4())

    async def post_thread(self, channel_id, id_, text):
        """No thread posting for null application"""
        return 200

    async def update_thread(self, channel_id, id_, status, body, header, status_icons, chain_enabled=True, status_enabled=True):
        """No thread updating for null application"""
        pass

    async def update(self, uuid_, incident, incident_status, alert_state, updated_status, chain_enabled, status_enabled):
        """No message updates for null application"""
        pass

    async def new_version_notification(self, channel_id, new_tag):
        """No version notifications for null application"""
        pass

    async def notify(self, incident, notify_type, identifier):
        """No notifications for null application"""
        return 200

    async def close(self):
        """No cleanup needed"""
        pass
