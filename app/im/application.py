import asyncio
from abc import ABC, abstractmethod
from typing import Union, Dict, Optional

from app.config.config import get_config
from app.config.validation import ApplicationConfig, MattermostUser, SlackUser, TelegramUser, MessengerType
from app.http_client import RateLimitedClient
from app.im.chain.chain_factory import ChainFactory
from app.im.groups import generate_user_groups
from app.im.template import JinjaTemplate, notification_user, notification_user_group, update_status, \
    notification_assignment, notification_unassignment
from app.logging import logger


class Application(ABC):

    def __init__(self, app_config: ApplicationConfig, channels, default_channel):
        self.http: Optional[RateLimitedClient] = None  # Will be initialized async
        self.type = app_config.type
        self.url = self.get_url(app_config)
        self.public_url = None  # Will be set in async initialization
        self.team = self.get_team_name(app_config)
        self._app_config = app_config  # Store for async initialization
        self.chains = ChainFactory.generate(app_config.chains)
        self.templates = app_config.template_files
        self.body_template, self.header_template, self.status_icons_template = self.generate_template()

        # Application-specific parameters
        self.post_message_url = None
        self.headers = None
        self.rate_limit = None
        self.rate_window = 1.0
        self.thread_id_key = None
        self._initialize_specific_params()

        self.channels = channels
        self.default_channel_id = self.channels[default_channel]['id']
        self.users = None  # Will be initialized async
        self.user_groups = None  # Will be initialized async
        self.admin_users = None  # Will be initialized async

        # Store config for async initialization
        self._users_config = app_config.users
        self._user_groups_config = app_config.user_groups
        self._admin_users_config = app_config.admin_users

    async def initialize_async(self):
        """Initialize async components after object creation"""
        self.http = self._setup_http()
        if hasattr(self, '_get_public_url') and callable(getattr(self, '_get_public_url')):
            if asyncio.iscoroutinefunction(self._get_public_url):
                self.public_url = await self._get_public_url(self._app_config)
            else:
                self.public_url = self._get_public_url(self._app_config)
        self.users = await self._generate_users(self._users_config)
        self.user_groups = generate_user_groups(self._user_groups_config, self.users)
        self.admin_users = [self.users[admin] for admin in self._admin_users_config]

    async def close(self):
        """Close the aiohttp session"""
        if self.http:
            await self.http.close()

    async def fetch_and_assign_user_name(self, incident, user_id, incidents=None):
        """
        Fetch user details and assign full name to incident.
        Uses incident cache to avoid redundant API calls when possible.

        Args:
            incident: The incident to assign the user name to
            user_id: The user ID to fetch the name for
            incidents: Optional incidents collection for caching lookup
        """
        try:
            if incidents:
                cached_name = incidents.get_assigned_user_by_id(user_id)
                if cached_name:
                    incident.assign_fullname(cached_name)
                    incident.dump()
                    logger.debug(f'Incident {incident.uuid} assigned cached user name: {cached_name}')
                    return

            user_details = await self.get_user_details({'id': user_id})
            assigned_name = user_details.get('full_name') or "(empty)"
            incident.assign_fullname(assigned_name)
            if user_details.get('username'):
                incident.assign_user(user_details.get('username'))
            incident.dump()
            logger.debug(f'Incident {incident.uuid} assigned user name from API: {assigned_name}')

        except Exception as e:
            logger.error(f'Failed to fetch and assign user name for incident {incident.uuid}: {e}')
            incident.assign_fullname("-")
            incident.dump()

    async def post_assignment_notification(self, incident_obj, user_id, user_display_name=None):
        """
        Post a notification message to the thread when a user is assigned to an incident.

        Args:
            incident_obj: The incident object
            user_id: The user ID that was assigned
            user_display_name: The display name of the user that was assigned
        """
        config = get_config()
        if not config.incident.notifications.assignment or not user_id:
            return

        try:
            header = self.header_template.form_message(incident_obj.payload, incident_obj)
            fields = {'type': self.type.value, 'username': user_display_name, 'id': user_id}
            text = JinjaTemplate(notification_assignment).form_notification(fields)
            if self.type == MessengerType.TELEGRAM:
                message = text
            else:
                message = header + '\n' + text

            await self.post_thread(incident_obj.channel_id, incident_obj.ts, message)
            logger.debug(f'Posted assignment notification for incident {incident_obj.uuid}')

        except Exception as e:
            logger.error(f'Failed to post assignment notification for incident {incident_obj.uuid}: {e}')

    async def post_unassignment_notification(self, incident_obj):
        """
        Post a notification message to the thread when a user is unassigned from an incident.

        Args:
            incident_obj: The incident object
        """
        config = get_config()
        if not config.incident.notifications.assignment:
            return

        try:
            header = self.header_template.form_message(incident_obj.payload, incident_obj)
            text = JinjaTemplate(notification_unassignment).form_notification({})
            if self.type.value == MessengerType.TELEGRAM:
                message = text
            else:
                message = header + '\n' + text

            await self.post_thread(incident_obj.channel_id, incident_obj.ts, message)
            logger.debug(f'Posted unassignment notification for incident {incident_obj.uuid}: {message}')

        except Exception as e:
            logger.error(f'Failed to post unassignment notification for incident {incident_obj.uuid}: {e}')

    def get_url(self, app_config: ApplicationConfig):
        return self._get_url(app_config)

    def get_team_name(self, app_config: ApplicationConfig):
        return self._get_team_name(app_config)

    async def _generate_users(self, users_dict: Dict[str, Union[SlackUser, MattermostUser, TelegramUser]]):
        logger.info('Creating users')

        users = {}
        for name, user_info in users_dict.items():
            if user_info.id is not None:
                user_details = await self.get_user_details(user_info)
                if not user_details['exists']:
                    logger.warning(f'.. user {name} not found in {self.type.value.capitalize()} and will not be notified')
            else:
                logger.warning(f'.. user {name} has no \'id\' and will not be notified')
                user_details = {}
            users[name] = self.create_user(name, user_details)

        return users

    def generate_template(self):
        def read_template(file_key, default_path):
            file_path = self.templates.get(file_key, default_path)
            return JinjaTemplate(open(file_path).read())

        body_template = read_template('body', f'./templates/{self.type.value}_body.j2')
        header_template = read_template('header', f'./templates/{self.type.value}_header.j2')
        status_icons_template = read_template('status_icons', f'./templates/{self.type.value}_status_icons.j2')

        return body_template, header_template, status_icons_template

    async def notify(self, incident, notify_type, identifier):
        destinations = self.get_notification_destinations()
        if notify_type == 'user':
            unit = self.users.get(identifier)
            text_template = JinjaTemplate(notification_user)
        else:
            unit = self.user_groups.get(identifier)
            text_template = JinjaTemplate(notification_user_group)
        fields = {'type': self.type.value, 'name': identifier, 'unit': unit, 'admins': destinations}
        text = text_template.form_notification(fields)
        header = self.header_template.form_message(incident.payload, incident)
        if self.type == MessengerType.TELEGRAM:
            message = text
        else:
            message = header + '\n' + text
        response_code = await self.post_thread(incident.channel_id, incident.ts, message)
        logger.info(f'Incident {incident.uuid} -> chain step {notify_type} \'{identifier}\'')
        return response_code

    async def update(self, uuid_, incident, incident_status, alert_state, updated_status, chain_enabled,
                     status_enabled):
        body = self.body_template.form_message(alert_state, incident)
        header = self.header_template.form_message(alert_state, incident)
        status_icons = self.status_icons_template.form_message(alert_state, incident)
        await self.update_thread(
            incident.channel_id, incident.ts, incident_status, body, header, status_icons, chain_enabled, status_enabled
        )
        if updated_status:
            logger.info(f'Incident {uuid_} updated with new status \'{incident_status}\'')
            # post to thread
            if status_enabled and incident_status != 'closed':
                header = self.header_template.form_message(incident.payload, incident)

                text_template = JinjaTemplate(update_status)
                admins = self.get_notification_destinations()
                fields = {'type': self.type.value, 'status': incident_status, 'admins': admins}
                text = text_template.form_notification(fields)

                if self.type == MessengerType.TELEGRAM:
                    message = text
                else:
                    message = header + '\n' + text
                await self.post_thread(incident.channel_id, incident.ts, message)

    async def create_thread(self, channel_id, body, header, status_icons, status):
        payload = self._create_thread_payload(channel_id, body, header, status_icons, status)
        return await self._send_create_thread(payload)

    async def _send_create_thread(self, payload):
        response = await self.http.post(self.post_message_url, headers=self.headers, json=payload)
        response_json = await response.json()
        response.close()
        return response_json.get(self.thread_id_key)

    async def update_thread(self, channel_id, id_, status, body, header, status_icons, chain_enabled=True,
                            status_enabled=True):
        payload = self.update_thread_payload(channel_id, id_, body, header, status_icons, status, chain_enabled,
                                             status_enabled)
        await self._update_thread(id_, payload)

    async def post_thread(self, channel_id, id_, text):
        payload = self._post_thread_payload(channel_id, id_, text)
        response = await self.http.post(self.post_message_url, headers=self.headers, json=payload)
        status = response.status
        response.close()
        return status

    def _setup_http(self) -> RateLimitedClient:
        """
        Setup HTTP client with rate limiting.
        
        Returns:
            RateLimitedClient instance
        """
        if self.rate_limit:
            logger.info(
                f"{self.type.value.capitalize()} rate limiting enabled: "
                f"{self.rate_limit} requests per {self.rate_window}s window"
            )
        else:
            logger.info(f"{self.type.value.capitalize()} rate limiting disabled")
        
        client = RateLimitedClient(
            rate_limit=self.rate_limit,
            rate_window=self.rate_window,
            retry_attempts=3,
            timeout=30.0,
            connector_limit=100,
            connector_limit_per_host=30
        )
        
        # Initialize the client
        client._initialize_client()
        
        return client

    @abstractmethod
    async def buttons_handler(self, payload, incidents, queue_, route):
        pass

    @abstractmethod
    def _initialize_specific_params(self):
        pass

    @abstractmethod
    def _markdown_links_to_native_format(self, text):
        pass

    @abstractmethod
    def _get_url(self, app_config: ApplicationConfig):
        pass

    @abstractmethod
    def _get_public_url(self, app_config: ApplicationConfig):
        """Get the public URL of the application to share with users."""
        pass

    @abstractmethod
    def _get_team_name(self, app_config: ApplicationConfig):
        pass

    @abstractmethod
    def get_notification_destinations(self):
        pass

    @abstractmethod
    def get_admins_text(self):
        pass

    @abstractmethod
    async def send_message(self, channel_id, text, attachment):
        pass

    @abstractmethod
    def _create_thread_payload(self, channel_id, body, header, status_icons, status):
        pass

    @abstractmethod
    def _post_thread_payload(self, channel_id, id_, text):
        pass

    @abstractmethod
    def update_thread_payload(self, channel_id, id_, body, header, status_icons, status, chain_enabled, status_enabled):
        pass

    @abstractmethod
    async def _update_thread(self, id_, payload):
        pass

    @abstractmethod
    async def get_user_details(self, user_info: Union[SlackUser, MattermostUser, TelegramUser, Dict]):
        """Fetch user-specific details (ID, name, etc.) from the system. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def create_user(self, name, user_details):
        """Create a user object specific to the application (Slack/Mattermost)."""
        pass
