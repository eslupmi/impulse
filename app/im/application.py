import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Union, Dict, Optional, TYPE_CHECKING

from app.config.config import get_config
from app.config.validation import ApplicationConfig, MattermostUser, SlackUser, TelegramUser, MessengerType
from app.http_client import RateLimitedClient
from app.im.chain.chain_factory import ChainFactory
from app.im.groups import Group
from app.im.template import notification_user, notification_user_group, notification_group, update_status, \
    notification_assignment, notification_unassignment, notification_freeze, notification_unfreeze
from app.im.user_groups import generate_user_groups
from app.im.user_store import get_user_store, UserUpdateScheduler
from app.im.users import UserManager
from app.incident.unfreeze import unfreeze_incident
from app.integrations.jira_integration import JiraIntegration
from app.jinja_template import JinjaTemplate
from app.logging import logger
from app.queue.constants import QueueItemType
from app.time import calculate_freeze_time, format_freeze_expiration

if TYPE_CHECKING:
    from app.incident.incident import Incident
    from app.queue.queue import AsyncQueue

log_button_pressed = 'Button pressed'


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
        self.groups = {}  # Groups (Slack/Mattermost only, empty for others)
        self.admin_users = None  # Will be initialized async

        # Store config for async initialization
        self._users_config = app_config.users
        self._user_groups_config = app_config.user_groups
        self._groups_config = getattr(app_config, 'groups', {})
        self._admin_users_config = app_config.admin_users

        # Track async tasks to prevent premature garbage collection
        self._async_tasks: set = set()
        
        # User update scheduler (set via configure_scheduler)
        self._user_scheduler: Optional[UserUpdateScheduler] = None

    def configure_scheduler(self, scheduler: UserUpdateScheduler) -> None:
        """Configure user update scheduler."""
        self._user_scheduler = scheduler

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
        self.groups = await self._generate_groups(self._groups_config)
        if self.groups:
            logger.info(f'Initialized {len(self.groups)} groups: {", ".join(self.groups.keys())}')
        self.admin_users = [self.users[admin] for admin in self._admin_users_config]

    @staticmethod
    def _build_full_name(stored_data: dict) -> str:
        first_name = stored_data.get('first_name') or ''
        last_name = stored_data.get('last_name') or ''
        full_name = f"{first_name} {last_name}".strip()
        return full_name or stored_data.get('username') or 'Unknown'

    async def close(self):
        """Close the aiohttp session"""
        if self.http:
            await self.http.close()

    async def fetch_and_assign_user_name(self, incident, user_id, dump=True):
        try:
            if self._try_assign_from_user_manager(incident, user_id):
                logger.debug(f'Incident {incident.uuid} assigned', extra={'user_id': user_id})
        except Exception as e:
            logger.error(f'Failed to fetch user name for incident {incident.uuid}: {e}')
        finally:
            if dump:
                incident.dump()

    def _try_assign_from_user_manager(self, incident, user_id):
        """Try to assign user from the user manager. Returns True if successful."""
        cached_user = self.users.get_user_by_id(user_id)
        if not (cached_user and cached_user.exists):
            return False
        incident.assigned_user_id = user_id
        incident.assigned_user = cached_user.username
        incident.assigned_fullname = cached_user.name
        return True

    @staticmethod
    def _format_display_name(user_details: dict) -> str:
        """Format user display name: Full Name → @username → (empty)."""
        full_name = user_details.get('full_name')
        if full_name:
            return full_name
        username = user_details.get('username')
        if username:
            return f"@{username}"
        return "(empty)"

    def _add_discovered_user(self, user_id, user_details):
        user_id_str = str(user_id)
        
        # Check if this is already a configured user
        existing_user = self.users.get_user_by_id(user_id)
        if existing_user and existing_user.defined:
            return
        
        user_store = get_user_store()
        user_store.save(user_id_str, self.type.value, user_details)
        
        display_name = self._format_display_name(user_details)
        user = self.create_user(display_name, user_details)
        if user:
            self.users.add_user(user_id_str, user)
            if self._user_scheduler:
                self._user_scheduler.schedule_update(user_id_str)

    async def post_assignment_notification(self, incident):
        config = get_config()
        if not config.incident.notifications.assignment or not incident.assigned_user_id:
            return

        try:
            header = self.header_template.form_message(incident.payload, incident)
            fields = {'type': self.type.value, 'username': incident.assigned_user, 'id': incident.assigned_user_id}
            text = JinjaTemplate(notification_assignment).form_notification(fields)
            if self.type == MessengerType.TELEGRAM:
                message = text
            else:
                message = header + '\n' + text

            await self.post_thread(incident.channel_id, incident.ts, message)
            logger.debug(f'Posted assignment notification for incident {incident.uuid}')

        except Exception as e:
            logger.error(f'Failed to post assignment notification for incident {incident.uuid}: {e}')

    async def post_unassignment_notification(self, incident_obj):
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

    def _handle_task_action(self, incident_, user_id, queue_):
        """Handle Task button action"""
        logger.info(log_button_pressed, extra={'uuid': incident_.uuid, 'button': 'task', 'user_id': user_id})
        self._track_async_task(asyncio.create_task(self.handle_task_button(incident_, queue_)))

    async def _handle_freeze_action(
            self, incident_: 'Incident', freeze_option: str, user_id: str, incidents, queue_: 'AsyncQueue',
            user_display_name: Optional[str] = None, user_timezone: Optional[str] = None
    ):
        """Handle freeze button action"""
        logger.info(log_button_pressed, extra={'uuid': incident_.uuid, 'button': 'freeze', 'user_id': user_id})
        
        config = get_config()
        timezone_str = user_timezone or config.app.general.timezone
        freeze_time = calculate_freeze_time(freeze_option, config.app.general, timezone_str)
        self._try_assign_from_user_manager(incident_, user_id)
        await self.fetch_and_assign_user_name(incident_, user_id, dump=False)
        incident_.freeze(freeze_time, user_id, user_display_name)
        
        await queue_.delete_by_id(incident_.uniq_id, delete_steps=True, delete_status=False)
        await queue_.put(freeze_time, QueueItemType.UNFREEZE, incident_.uniq_id)
        self._track_async_task(asyncio.create_task(self._post_freeze_notification(incident_, freeze_time, timezone_str)))

    async def _handle_unfreeze_action(self, incident_: 'Incident', user_id: str, queue_: 'AsyncQueue'):
        """Handle unfreeze button action - schedule unfreeze via queue"""
        logger.info(log_button_pressed, extra={'uuid': incident_.uuid, 'button': 'unfreeze', 'user_id': user_id})
        await queue_.delete_by_id_and_type(incident_.uniq_id, QueueItemType.UNFREEZE)
        await unfreeze_incident(incident_, self, queue_)


    async def _post_freeze_notification(self, incident_: 'Incident', freeze_time: datetime, user_timezone: str = "UTC"):
        """Post freeze notification to thread"""
        text_template = JinjaTemplate(notification_freeze)
        fields = {'type': self.type.value, 'frozen_until': format_freeze_expiration(freeze_time, user_timezone)}
        text = text_template.form_notification(fields)
        
        if self.type != MessengerType.TELEGRAM:
            header = self.header_template.form_message(incident_.payload, incident_)
            message = header + '\n' + text
        else:
            message = text
            
        await self.post_thread(incident_.channel_id, incident_.ts, message)

    async def _post_unfreeze_notification(self, incident_: 'Incident'):
        """Post unfreeze notification to thread"""
        text_template = JinjaTemplate(notification_unfreeze)
        text = text_template.form_notification({'type': self.type.value})
        
        if self.type != MessengerType.TELEGRAM:
            header = self.header_template.form_message(incident_.payload, incident_)
            message = header + '\n' + text
        else:
            message = text
            
        await self.post_thread(incident_.channel_id, incident_.ts, message)

    def get_configured_user_name(self, user_id, fallback_name):
        """Get user name from configuration, or use fallback name"""
        if self.users is None:
            return fallback_name
        user = self.users.get_user_by_id(user_id)
        return user.name if user and user.exists else fallback_name

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
        """Load users from UserStore, then fetch missing configured users from API."""
        logger.info('Creating users')
        user_store = get_user_store()
        messenger_type = self.type.value

        user_manager = UserManager()
        stored_user_ids = self._load_stored_users(user_manager, user_store, messenger_type)
        
        for name, user_info in users_dict.items():            
            user_id = str(user_info.id)
            if user_id in stored_user_ids:
                user_manager.add_config_name(name, user_id)
                continue
            
            user_details = await self.get_user_details(user_info)
            if not user_details['exists']:
                logger.warning('User not found in messenger', extra={'user': name})
            else:
                user_store.save(user_id, messenger_type, user_details)
            user = self.create_user(name, user_details)
            user_manager.add_user(user_id, user, config_name=name)

        return user_manager

    def _load_stored_users(self, user_manager: UserManager, user_store, messenger_type: str) -> set:
        """Load ALL stored users for this messenger type into UserManager. Returns set of loaded user IDs."""
        stored_users = user_store.get_all_users_by_type(messenger_type)
        loaded_ids = set()
        
        for user_id, stored_data in stored_users.items():
            user_details = self._stored_data_to_user_details(user_id, stored_data)
            display_name = self._format_display_name(user_details)
            user = self.create_user(display_name, user_details)
            if user:
                user_manager.add_user(user_id, user)
                loaded_ids.add(user_id)
        
        if loaded_ids:
            logger.info(f'Loaded {len(loaded_ids)} users from storage')
        
        return loaded_ids

    def _stored_data_to_user_details(self, user_id: str, stored_data: dict) -> dict:
        """Convert stored data to user_details format."""
        full_name = self._build_full_name(stored_data)
        return {
            'id': user_id,
            'exists': True,
            'full_name': full_name,
            'username': stored_data.get('username'),
        }

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
        elif notify_type == 'user_group':
            unit = self.user_groups.get(identifier)
            text_template = JinjaTemplate(notification_user_group)
        elif notify_type == 'group':
            unit = self.groups.get(identifier)
            text_template = JinjaTemplate(notification_group)
        else:
            unit = None
            text_template = JinjaTemplate(notification_user_group)
        fields = {'type': self.type.value, 'name': identifier, 'unit': unit, 'admins': destinations}
        text = text_template.form_notification(fields)
        _, header, _ = self.form_incident_message(incident)
        if self.type == MessengerType.TELEGRAM:
            message = text
        else:
            message = header + '\n' + text
        response_code = await self.post_thread(incident.channel_id, incident.ts, message)
        logger.info(f'Chain step {notify_type} \'{identifier}\'', extra={'uuid': incident.uuid})
        return response_code

    async def update(self, incident, incident_status, alert_state, updated_status, chain_enabled,
                     frozen_until, task_link=''):
        # Update thread starter message (skip if frozen)
        if not incident.is_frozen():
            await self.update_thread(incident)

            # post to thread (skip if frozen)
            config = get_config()
            if updated_status and incident_status != 'closed' and config.incident.notifications.status_update:
                text_template = JinjaTemplate(update_status)
                admins = self.get_notification_destinations()
                fields = {'type': self.type.value, 'status': incident_status, 'admins': admins}
                text = text_template.form_notification(fields)

                _, header, _ = self.form_incident_message(incident)
                message = text if self.type == MessengerType.TELEGRAM else header + '\n' + text
                await self.post_thread(incident.channel_id, incident.ts, message)

    def form_incident_message(self, incident):
        """Render body, header, and status_icons templates for an incident."""
        body = self.body_template.form_message(incident.payload, incident)
        header = self.header_template.form_message(incident.payload, incident)
        status_icons = self.status_icons_template.form_message(incident.payload, incident)
        return body, header, status_icons

    async def create_thread(self, incident, body, header, status_icons):
        payload = self._create_thread_payload(incident, body, header, status_icons)
        return await self._send_create_thread(payload)

    async def _send_create_thread(self, payload):
        response = await self.http.post(self.post_message_url, headers=self.headers, json=payload)
        response_json = await response.json()
        response.close()
        return response_json.get(self.thread_id_key)

    async def update_thread(self, incident):
        body, header, status_icons = self.form_incident_message(incident)

        payload = self.update_thread_payload(incident, body, header, status_icons)
        await self._update_thread(incident.ts, payload)

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
            logger.debug(
                f"Rate limit: "
                f"{self.rate_limit} requests per {self.rate_window}s", extra={'messenger': self.type.value}
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
        client.initialize_client()
        return client

    @abstractmethod
    async def buttons_handler(self, payload, incidents, queue_, route):
        pass

    @abstractmethod
    async def _generate_groups(self, groups_dict: Dict):
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
    def _create_thread_payload(self, incident, body, header, status_icons):
        pass

    @abstractmethod
    def _post_thread_payload(self, channel_id, id_, text):
        pass

    @abstractmethod
    def update_thread_payload(self, incident, body, header, status_icons):
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

    @abstractmethod
    async def get_all_groups(self):
        pass

    def create_group(self, config_name, group_details):
        """Create a Group object from group details. Default implementation for Slack and Mattermost."""
        group_id = group_details.get('id') if group_details.get('exists') else None
        group_name = group_details.get('name')
        return Group(
            config_name=config_name,
            name=group_name,
            id_=group_id,
            exists=group_details.get('exists', False)
        )
