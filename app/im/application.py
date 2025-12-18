import asyncio
from abc import ABC, abstractmethod
from typing import Union, Dict, Optional, TYPE_CHECKING
from datetime import datetime

from app.config.config import get_config
from app.config.validation import ApplicationConfig, MattermostUser, SlackUser, TelegramUser, MessengerType
from app.http_client import RateLimitedClient
from app.im.chain.chain_factory import ChainFactory
from app.im.groups import generate_user_groups
from app.im.template import notification_user, notification_user_group, update_status, \
    notification_assignment, notification_unassignment, notification_freeze, notification_unfreeze
from app.jinja_template import JinjaTemplate
from app.logging import logger
from app.integrations.jira_integration import JiraIntegration
from app.queue.constants import QueueItemType
from app.time import calculate_freeze_time, format_freeze_expiration
from datetime import datetime, timezone

if TYPE_CHECKING:
    from app.incident.incident import Incident
    from app.queue.queue import AsyncQueue


class Application(ABC):
    task_management_integration: Optional[JiraIntegration] = None

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

        # Track async tasks to prevent premature garbage collection
        self._async_tasks: set = set()

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

    async def fetch_and_assign_user_name(self, incident, user_id, incidents=None, dump=True):
        """
        Fetch user details and assign full name to incident.
        Uses incident cache to avoid redundant API calls when possible.

        Args:
            incident: The incident to assign the user name to
            user_id: The user ID to fetch the name for
            incidents: Optional incidents collection for caching lookup
            dump: Whether to dump the incident after assigning the user name
        """
        try:
            if incidents:
                cached_name = incidents.get_assigned_user_by_id(user_id)
                if cached_name:
                    incident.assign_fullname(cached_name)
                    if dump:
                        incident.dump()
                    logger.debug(f'Incident {incident.uuid} assigned cached user name: {cached_name}')
                    return

            user_details = await self.get_user_details({'id': user_id})
            assigned_name = user_details.get('full_name') or "(empty)"
            incident.assign_fullname(assigned_name)
            if user_details.get('username'):
                incident.assign_user(user_details.get('username'))
            if dump:
                incident.dump()
            logger.debug(f'Incident {incident.uuid} assigned user name from API: {assigned_name}')

        except Exception as e:
            logger.error(f'Failed to fetch and assign user name for incident {incident.uuid}: {e}')
            incident.assign_fullname("-")
            if dump:
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

    def _track_async_task(self, task):
        """
        Track an async task to prevent premature garbage collection.

        Args:
            task: asyncio.Task object to track
        """
        if not hasattr(self, '_async_tasks'):
            self._async_tasks = set()
        self._async_tasks.add(task)
        task.add_done_callback(self._async_tasks.discard)

    def _handle_status_action(self, incident_, set_status_to):
        """Handle status-related button actions"""
        logger.info(f'Incident {incident_.uuid} -> button STATUS pressed ({"enabled" if set_status_to else "disabled"})')
        incident_.status_enabled = set_status_to

    def _handle_task_action(self, incident_, queue_):
        """Handle Task button action"""
        logger.info(f'Incident {incident_.uuid} -> button TASK pressed')
        self._track_async_task(asyncio.create_task(self.handle_task_button(incident_, queue_)))

    def _should_include_header_in_notifications(self) -> bool:
        """
        Determine if header should be included in freeze/unfreeze notifications.
        Override in subclass if different behavior is needed (e.g., Telegram returns False).
        """
        return True

    async def _handle_freeze_action(self, incident_: 'Incident', freeze_option: str, user_id: str, incidents, queue_: 'AsyncQueue', user_display_name: Optional[str] = None, user_timezone: Optional[str] = None):
        """Handle freeze button action"""
        config = get_config()
        timezone_str = user_timezone or config.messenger.timezone
        freeze_time = calculate_freeze_time(freeze_option, config.app.general, timezone_str)

        incident_.assign_user_id(user_id)
        if user_display_name:
            incident_.assign_user(user_display_name)
        await self.fetch_and_assign_user_name(incident_, user_id, incidents, dump=False)
        incident_.freeze(freeze_time, user_id, user_display_name)
        
        logger.info(f'Incident {incident_.uuid} -> FREEZE with option {freeze_option}, frozen until {freeze_time} (timezone: {timezone_str})')
        
        await queue_.delete_by_id(incident_.uniq_id, delete_steps=True, delete_status=False)
        await queue_.put(freeze_time, QueueItemType.UNFREEZE, incident_.uniq_id)
        self._track_async_task(asyncio.create_task(self._post_freeze_notification(incident_, freeze_time, timezone_str)))

    async def _handle_unfreeze_action(self, incident_: 'Incident', queue_: 'AsyncQueue'):
        """Handle unfreeze button action - schedule unfreeze via queue"""
        logger.info(f'Incident {incident_.uuid} -> UNFREEZE pressed')
        await queue_.delete_by_id_and_type(incident_.uniq_id, QueueItemType.UNFREEZE)
        await queue_.put_first(datetime.now(timezone.utc), QueueItemType.UNFREEZE, incident_.uniq_id)

    async def _post_freeze_notification(self, incident_: 'Incident', freeze_time: datetime, user_timezone: str = "UTC"):
        """Post freeze notification to thread"""
        text_template = JinjaTemplate(notification_freeze)
        fields = {'type': self.type.value, 'frozen_until': format_freeze_expiration(freeze_time, user_timezone)}
        text = text_template.form_notification(fields)
        
        if self._should_include_header_in_notifications():
            header = self.header_template.form_message(incident_.payload, incident_)
            message = header + '\n' + text
        else:
            message = text
            
        await self.post_thread(incident_.channel_id, incident_.ts, message)

    async def _post_unfreeze_notification(self, incident_: 'Incident'):
        """Post unfreeze notification to thread"""
        text_template = JinjaTemplate(notification_unfreeze)
        text = text_template.form_notification({'type': self.type.value})
        
        if self._should_include_header_in_notifications():
            header = self.header_template.form_message(incident_.payload, incident_)
            message = header + '\n' + text
        else:
            message = text
            
        await self.post_thread(incident_.channel_id, incident_.ts, message)

    async def handle_task_button(self, incident, queue_):
        """
        Handle Task button press for an incident.

        Args:
            incident: Incident object
            queue_: Queue manager

        Returns:
            Response dict with success status
        """
        if not self.task_management_integration:
            logger.error("Task management integration not initialized")
            return {"success": False, "message": "Task management integration not available"}

        return await self.task_management_integration.handle_button_press(incident, queue_)

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

    async def update(self, incident, incident_status, alert_state, updated_status, chain_enabled,
                     frozen_until, task_link=''):
        # Update thread starter message (skip if frozen)
        if not incident.is_frozen():
            body = self.body_template.form_message(alert_state, incident)
            header = self.header_template.form_message(alert_state, incident)
            status_icons = self.status_icons_template.form_message(alert_state, incident)
            await self.update_thread(
                incident.channel_id, incident.ts, incident_status, body, header, status_icons, chain_enabled, frozen_until, task_link
            )

        if updated_status:
            logger.info(f'Incident {incident.uuid} updated with new status \'{incident_status}\'')
            # post to thread (skip if frozen)
            config = get_config()
            if not incident.is_frozen() and incident_status != 'closed' and config.incident.notifications.status_update:
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
                            frozen_until=None, task_link=''):
        payload = self.update_thread_payload(channel_id, id_, body, header, status_icons, status, chain_enabled,
                                             frozen_until, task_link)
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
    def _create_thread_payload(self, channel_id, body, header, status_icons, status):
        pass

    @abstractmethod
    def _post_thread_payload(self, channel_id, id_, text):
        pass

    @abstractmethod
    def update_thread_payload(self, channel_id, id_, body, header, status_icons, status, chain_enabled, frozen_until, task_link=''):
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
        pass
