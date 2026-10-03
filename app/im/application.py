import asyncio
from fastapi.responses import Response
from dataclasses import asdict
from datetime import datetime
from typing import TYPE_CHECKING

from jinja2 import TemplateError

from app.config.config import get_config
from app.config.environment import get_environment_config
from app.http_client.errors import MESSENGER_TRANSPORT_ERRORS
from app.http_client.rate_limited_client import RateLimitedClient
from app.im.chain.chain_factory import ChainFactory
from app.im.groups import Group
from app.im.interactions import apply_interaction
from impulse_messenger_api import (
    BaseApplicationConfig, IncidentPresentation, MessageRef, MessengerProvider, NotificationContent,
    ProviderContext, ProviderIdentity, UserProfile, InteractiveProvider, InteractionRequest, ProviderResponse,
)
from app.im.messenger_init import messenger_init_step_async, messenger_init_step_sync
from app.im.template import (
    assignment_template_context,
    chain_step_group,
    chain_step_user,
    chain_step_user_group,
    chain_template_context,
    freeze_template_context,
    incident_notifications_assignment,
    incident_notifications_freeze,
    incident_notifications_status_update,
    incident_notifications_unfreeze,
    status_update_template_context,
)
from app.im.user_groups import generate_user_groups
from app.im.user_store import UserUpdateScheduler, get_user_store
from app.im.users import BaseUser, UserManager, ProfileUser
from app.incident.freeze import FreezeSource
from app.incident.incident import unfreeze_incident
from app.integrations.jira_integration import JiraIntegration
from app.jinja_template import JinjaTemplate
from app.logging import logger
from app.logging_context import redact_messenger_url
from app.queue.constants import QueueItemType
from app.time import calculate_freeze_time, format_freeze_expiration

if TYPE_CHECKING:
    from app.incident.incident import Incident
    from app.queue.queue import AsyncQueue

log_button_pressed = 'Button pressed'


class Application:
    task_management_integration: JiraIntegration | None = None

    def __init__(self, app_config: BaseApplicationConfig, channels, default_channel, webhooks=None,
                 *, provider: MessengerProvider):
        self.provider = provider
        self.http: RateLimitedClient | None = None
        self.type = app_config.type
        self.url = provider.url.rstrip('/')
        self.public_url = None
        self.team = provider.team
        self._app_config = app_config
        self.chains = ChainFactory.generate(
            app_config.chains,
            users=app_config.users or {},
            user_groups=app_config.user_groups or {},
            groups=app_config.groups or {},
            webhooks=webhooks or {},
        )
        self.templates = app_config.template_files
        self.body_template, self.header_template, self.status_icons_template = self.generate_template()

        self.channels = channels
        self.default_channel_id = self.channels[default_channel]['id']
        self.users: UserManager | None = None
        self.user_groups = None
        self.groups: dict = {}
        self.admin_users = None
        self.webhooks: dict = {}

        self._users_config = app_config.users
        self._user_groups_config = app_config.user_groups
        self._groups_config = app_config.groups
        self._admin_users_config = app_config.admin_users

        self._async_tasks: set = set()
        
        self._user_scheduler: UserUpdateScheduler | None = None

    async def buttons_handler(self, payload, incidents, queue_):
        if not self.provider.descriptor.messaging_enabled:
            return Response(b'{}', status_code=200, media_type='application/json')
        if not isinstance(payload, InteractionRequest):
            raise TypeError('Provider callbacks require an InteractionRequest')
        provider = self.provider
        if not isinstance(provider, InteractiveProvider):
            raise TypeError(f'{provider.descriptor.provider_id} does not accept callbacks')
        result = await provider.parse_interaction(payload)
        if not isinstance(result, ProviderResponse):
            result = await apply_interaction(self, result, incidents, queue_)
        return Response(result.body, status_code=result.status_code, media_type=result.media_type)

    async def close(self):
        if self.http:
            await self.http.close()

    def configure_scheduler(self, scheduler: UserUpdateScheduler) -> None:
        self._user_scheduler = scheduler

    def create_group(self, config_name, group_details):
        return Group(
            config_name=config_name,
            name=group_details.get('name'),
            id_=group_details.get('id'),
            exists=group_details.get('exists', False)
        )

    async def create_incident_message(self, incident, body, header, status_icons):
        message = self._presentation(incident, body, header, status_icons)
        result = await self.provider.create_incident(message)
        return result.thread_id if result else None

    def create_user(self, name, user_details):
        profile = UserProfile(
            id=user_details.get('id'), exists=bool(user_details.get('exists', False)),
            full_name=user_details.get('full_name'), username=user_details.get('username'),
            email=user_details.get('email'), timezone=user_details.get('timezone'),
        )
        notification_id = self.provider.mention_id(profile) if isinstance(self.provider, InteractiveProvider) else profile.id
        return ProfileUser(name=name, id_=user_details.get('id'), exists=user_details.get('exists', False),
                           full_name=user_details.get('full_name'), username=user_details.get('username'),
                           email=user_details.get('email'), timezone_=user_details.get('timezone'),
                           notification_id=notification_id,
                           serializer=getattr(self.provider, 'serialize_user', None))

    async def fetch_and_assign_user_name(self, incident, user_id, dump=True):
        user = self.users.get_user_by_id(user_id)
        if not (user and user.exists):
            user = await self._assign_from_api(user_id)
        if user is not None:
            incident.assigned_user_id = user_id
            incident.assigned_user = user.username
            incident.assigned_fullname = user.full_name or '(empty)'
            logger.debug(f'Incident {incident.uniq_id} assigned', extra={'user_id': user_id})
        if dump:
            incident.dump()

    async def _assign_from_api(self, user_id):
        try:
            user_details = await self.get_user_details(user_id)
        except MESSENGER_TRANSPORT_ERRORS as error:
            logger.error('Failed to fetch user for assignment', extra={'user_id': user_id, 'error': str(error)})
            return None
        if not user_details['exists']:
            logger.warning('User not found, assignment skipped', extra={'user_id': user_id})
            return None
        return self._add_discovered_user(user_id, user_details)

    def form_body_header_status_icons(self, incident):
        body = self.body_template.form_message(incident.payload, incident)
        header = self.header_template.form_message(incident.payload, incident)
        status_icons = self.status_icons_template.form_message(incident.payload, incident)
        return body, header, status_icons

    def notification_template(self, source):
        return JinjaTemplate(source, autoescape=self.provider.descriptor.html_autoescape)

    def notification_header(self, incident):
        if not self.provider.descriptor.notification_headers:
            return None
        return self.header_template.form_message(incident.payload, incident)

    def generate_template(self):
        if not self.provider.descriptor.messaging_enabled:
            return JinjaTemplate(''), JinjaTemplate(''), JinjaTemplate('')
        provider = self.provider
        if not isinstance(provider, InteractiveProvider):
            raise TypeError(f'{provider.descriptor.provider_id} does not provide templates')

        def read_template(file_key):
            file_path = self.templates.get(file_key) if self.templates else None
            if file_path:
                with open(file_path) as source:
                    return self.notification_template(source.read())
            return self.notification_template(provider.template_source(file_key))

        body_template = read_template('body')
        header_template = read_template('header')
        status_icons_template = read_template('status_icons')

        return body_template, header_template, status_icons_template

    async def get_all_groups(self):
        return {group.id: group.name for group in await self.provider.fetch_groups()}

    def get_config_name_by_user_id(self, user_id: int | str) -> str | None:
        str_user_id = str(user_id)
        for config_name, user_info in self._users_config.items():
            if str(user_info.id) == str_user_id:
                return config_name
        return None

    def get_notification_destinations(self):
        if not self.provider.descriptor.messaging_enabled:
            return []
        return [a.get_notification_identifier() for a in self.admin_users]

    async def get_user_details(self, user_id: str | int):
        assert isinstance(user_id, (str, int))
        return asdict(await self.provider.fetch_user(user_id))

    async def handle_task_button(self, incident, queue_):
        if not self.task_management_integration:
            logger.error("Task management integration not initialized")
            return {"success": False, "message": "Task management integration not available"}

        return await self.task_management_integration.handle_button_press(incident, queue_)

    async def handle_ui_assignment(self, incident, user_id, queue, ui_user=None):
        str_user_id = str(user_id)
        if incident.assigned_user_id == str_user_id:
            return False

        await queue.delete_by_id(incident.uniq_id, delete_steps=True, delete_status=False)
        await self.fetch_and_assign_user_name(incident, str_user_id)
        self.track_async_task(asyncio.create_task(self.post_assignment_notification(incident, ui_user=ui_user)))
        incident.chain_enabled = False
        incident.dump()
        await self.update_incident_message(incident)
        return True

    async def handle_ui_unassign(self, incident, queue, ui_user=None):
        if not incident.assigned_user_id:
            return False

        await queue.delete_by_id(incident.uniq_id, delete_steps=True, delete_status=False)
        incident.assigned_user_id = ""
        incident.assigned_user = ""
        incident.assigned_fullname = ""
        incident.chain_enabled = True
        self.track_async_task(asyncio.create_task(self.post_unassignment_notification(incident, ui_user=ui_user)))
        incident.dump()
        await self.update_incident_message(incident)
        return True

    async def handle_ui_freeze(self, incident, freeze_option, user_id, incidents, queue, user_timezone=None, ui_user=None):
        await self._handle_freeze_action(
            incident, freeze_option, user_id, incidents, queue, user_timezone=user_timezone, ui_user=ui_user,
        )
        await self.update_incident_message(incident)

    async def handle_ui_unfreeze(self, incident, queue):
        await self._handle_unfreeze_action(incident, '', queue)

    async def handle_ui_release(self, incident, ui_user=None):
        incident.release()
        self.track_async_task(asyncio.create_task(self.post_unassignment_notification(incident, ui_user=ui_user)))
        await self.update_incident_message(incident)

    async def initialize_async(self):
        if not self.provider.descriptor.messaging_enabled:
            self.public_url = ''
            self.users = UserManager()
            self.user_groups = {}
            self.groups = {}
            return
        redact_url = getattr(self.provider, 'redact_url', redact_messenger_url)
        logger.info(
            'Initializing messenger',
            extra={'messenger': self.type, 'url': redact_url(self.url)},
        )

        self.http = self._init_http_client()
        self.public_url = await self._init_public_url()
        self.users = await self._init_users()
        self.user_groups = self._init_user_groups()
        self.groups = await self._init_groups()
        if self.groups:
            logger.debug(f'Initialized {len(self.groups)} groups: {", ".join(self.groups.keys())}')
        self.admin_users = self._init_admin_users()

        await self.provider.activate()
        logger.info('Messenger initialized', extra={'messenger': self.type})

    @messenger_init_step_sync('http_client')
    def _init_http_client(self) -> RateLimitedClient:
        return self._setup_http()

    @messenger_init_step_async('public_url')
    async def _init_public_url(self):
        address = getattr(self._app_config, 'impulse_address', None)
        callback_url = f'{address}/app' if address else None
        assert self.http is not None
        identity = await self.provider.initialize(ProviderContext(self.http, callback_url))
        self.team = identity.team
        url = identity.public_url
        return url.rstrip("/") if url else url

    @messenger_init_step_async('users')
    async def _init_users(self):
        return await self._generate_users(self._users_config)

    @messenger_init_step_sync('user_groups')
    def _init_user_groups(self):
        return generate_user_groups(self._user_groups_config, self.users)

    @messenger_init_step_async('groups')
    async def _init_groups(self):
        return await self._generate_groups(self._groups_config)

    def _apply_admin_role(self, user, config_name):
        user.roles = ['admin'] if config_name in self._admin_users_config else []

    @messenger_init_step_sync('admin_users')
    def _init_admin_users(self):
        admins = []
        for admin in self._admin_users_config:
            user = self.users.get(admin)
            if user is None:
                logger.warning('Admin user not found', extra={'user': admin})
                continue
            self._apply_admin_role(user, admin)
            admins.append(user)
        return admins

    async def notify(self, incident, step):
        if not self.provider.descriptor.messaging_enabled:
            return 200
        messenger = self.type
        notify_type = step['name']
        if notify_type == 'user':
            text_template = self.notification_template(chain_step_user[messenger])
        elif notify_type == 'user_group':
            text_template = self.notification_template(chain_step_user_group[messenger])
        elif notify_type == 'group':
            text_template = self.notification_template(chain_step_group[messenger])
        else:
            text_template = self.notification_template(chain_step_user_group[messenger])
        text = text_template.form_notification(**chain_template_context(self, incident, step))
        header = self.notification_header(incident)
        response_code = await self._post_notification(incident, header, text)
        logger.info(f'Chain step {notify_type} \'{step["value"]}\'', extra={'uniq_id': incident.uniq_id})
        return response_code

    async def post_assignment_notification(self, incident, ui_user=None):
        config = get_config()
        if not config.incident.notifications.assignment or not incident.assigned_user_id:
            return

        try:
            header = self.notification_header(incident)
            text = self.notification_template(incident_notifications_assignment[self.type]).form_notification(
                **assignment_template_context(self, incident, ui_user)
            )
            await self._post_notification(incident, header, text)
            logger.debug(f'Posted assignment notification for incident {incident.uniq_id}')

        except MESSENGER_TRANSPORT_ERRORS + (TemplateError, KeyError) as e:
            logger.error(f'Failed to post assignment notification for incident {incident.uniq_id}: {e}')

    async def _post_notification(self, incident, header, text):
        result = await self.provider.post_notification(
            MessageRef(incident.channel_id, incident.ts), NotificationContent(text=text, header=header),
        )
        return result.status_code

    async def post_unassignment_notification(self, incident_obj, ui_user=None):
        config = get_config()
        if not config.incident.notifications.assignment:
            return

        try:
            header = self.notification_header(incident_obj)
            text = self.notification_template(incident_notifications_assignment[self.type]).form_notification(
                **assignment_template_context(self, incident_obj, ui_user)
            )
            await self._post_notification(incident_obj, header, text)
            logger.debug(f'Posted unassignment notification for incident {incident_obj.uniq_id}')

        except MESSENGER_TRANSPORT_ERRORS + (TemplateError, KeyError) as e:
            logger.error(f'Failed to post unassignment notification for incident {incident_obj.uniq_id}: {e}')

    async def post_freeze_notification(self, incident_: 'Incident', ui_user=None):
        if not self.provider.descriptor.messaging_enabled:
            return
        config = get_config()
        if not config.incident.notifications.freeze:
            return

        text = self.notification_template(incident_notifications_freeze[self.type]).form_notification(
            **freeze_template_context(incident_, ui_user)
        )
        header = self.notification_header(incident_)
        await self._post_notification(incident_, header, text)

    async def post_unfreeze_notification(self, incident_: 'Incident', ui_user=None):
        if not self.provider.descriptor.messaging_enabled:
            return
        text = self.notification_template(incident_notifications_unfreeze[self.type]).form_notification(
            **freeze_template_context(incident_, ui_user)
        )

        header = self.notification_header(incident_)
        await self._post_notification(incident_, header, text)

    def track_async_task(self, task):
        self._async_tasks.add(task)
        task.add_done_callback(self._async_tasks.discard)

    async def update(self, incident, incident_status, alert_state, updated_status, chain_enabled,
                     frozen_until, task_link='', previous_payload=None):
        if not self.provider.descriptor.messaging_enabled:
            return
        if not incident.is_frozen:
            await self.update_incident_message(incident)

            config = get_config()
            if updated_status and incident_status != 'closed' and config.incident.notifications.status_update:
                text_template = self.notification_template(incident_notifications_status_update[self.type])
                text = text_template.form_notification(
                    **status_update_template_context(self, incident, alert_state, previous_payload)
                )

                header = self.notification_header(incident)
                await self._post_notification(incident, header, text)

    async def update_incident_message(self, incident):
        if not self.provider.descriptor.messaging_enabled:
            return
        body, header, status_icons = self.form_body_header_status_icons(incident)
        tz_str = self._get_user_timezone_str(incident.assigned_user_id)
        await self.provider.update_incident(self._presentation(incident, body, header, status_icons, tz_str))

    @staticmethod
    def _presentation(incident, body, header, status_icons, tz_str=None):
        return IncidentPresentation(
            channel_id=incident.channel_id, thread_id=incident.ts, status=incident.status,
            header=header, body=body, status_icon=status_icons, chain_enabled=incident.chain_enabled,
            frozen=incident.is_frozen, frozen_by_inhibition=incident.frozen_by_inhibition,
            frozen_by_maintenance=incident.frozen_by_maintenance,
            frozen_until=incident.frozen_until.isoformat() if incident.frozen_until else None,
            can_unfreeze=incident.can_manual_unfreeze(), task_link=incident.task_link, timezone=tz_str,
            frozen_until_text=(format_freeze_expiration(incident.frozen_until, tz_str or get_config().app.general.timezone)
                               if incident.frozen_until else None),
            can_create_task=bool(get_config().app.task_management and get_environment_config().task_management_enabled),
        )

    ### PRIVATE METHODS ###

    def _add_discovered_user(self, user_id, user_details):
        user_id_str = str(user_id)
        existing_user = self.users.get_user_by_id(user_id)
        if existing_user and existing_user.exists:
            return existing_user

        get_user_store().save(user_id_str, self.type, user_details)
        config_name = self.get_config_name_by_user_id(user_id_str)
        user = self.create_user(self._format_display_name(user_details), user_details)
        self._apply_admin_role(user, config_name)
        self.users.add_user(user_id_str, user, config_name=config_name)
        if self._user_scheduler:
            self._user_scheduler.schedule_update(user_id_str)
        return user

    @staticmethod
    def _format_display_name(user_details: dict) -> str:
        full_name = user_details.get('full_name')
        if full_name:
            return full_name
        username = user_details.get('username')
        if username:
            return f"@{username}"
        return "(empty)"

    async def _generate_groups(self, groups_dict: dict):
        if not groups_dict:
            return {}
        all_groups = await self.get_all_groups()
        groups = {}
        for name, info in groups_dict.items():
            group_name = all_groups.get(info.id)
            if group_name is None:
                logger.warning('Group not found in messenger', extra={'group': name})
            groups[name] = self.create_group(name, {'id': info.id, 'name': group_name, 'exists': group_name is not None})
        return groups

    async def _generate_users(self, users_dict: dict):
        logger.info('Creating users')
        user_store = get_user_store()
        messenger_type = self.type

        user_manager = UserManager()
        stored = self._load_stored_users(user_store, messenger_type)

        for name, user_info in users_dict.items():
            user_id = str(user_info.id)
            if user_id in stored:
                user = self.create_user(name, stored[user_id])
                self._apply_admin_role(user, name)
                user_manager.add_user(user_id, user, config_name=name)
                continue

            user_details = await self.get_user_details(user_info.id)
            if not user_details['exists']:
                logger.warning('User not found in messenger', extra={'user': name})
            else:
                user_store.save(user_id, messenger_type, user_details)
            user = self.create_user(name, user_details)
            self._apply_admin_role(user, name)
            user_manager.add_user(user_id, user, config_name=name)

        return user_manager

    def _get_user_timezone_str(self, user_id: str | None = None) -> str:
        if user_id and self.users:
            user_tz = self.users.get_user_timezone(user_id)
            if user_tz:
                return user_tz
        return get_config().app.general.timezone

    @staticmethod
    def get_incident_link(provider_id, channel_id, thread_id, public_url, team=None):
        from app.im.registry import get_provider_registry
        try:
            registration = get_provider_registry().resolve(provider_id)
        except ValueError:
            return None
        if registration.incident_url:
            return registration.incident_url(MessageRef(channel_id, thread_id), ProviderIdentity(public_url, team))
        return None

    def get_user_profile_url(self, user_id: str, user: BaseUser) -> str | None:
        profile = UserProfile(id=str(user_id), exists=user.exists, username=user.username)
        return self.provider.user_url(profile, ProviderIdentity(self.public_url, self.team))

    async def apply_time_freeze(
            self, incident_: 'Incident', until: datetime, user, queue_: 'AsyncQueue',
            source: FreezeSource,
    ):
        """Core time-based freeze used by manual freeze, maintenance and other auto sources."""
        incident_.freeze(until, user, source)
        await queue_.delete_by_id(incident_.uniq_id, delete_steps=True, delete_status=False)
        await queue_.put(until, QueueItemType.UNFREEZE, incident_.uniq_id, data=source.value)

    async def _handle_freeze_action(
            self, incident_: 'Incident', freeze_option: str, user_id: str, incidents, queue_: 'AsyncQueue',
            user_timezone: str | None = None, ui_user=None,
    ):
        if not self.provider.descriptor.messaging_enabled:
            return
        logger.info(log_button_pressed, extra={'uniq_id': incident_.uniq_id, 'button': 'freeze', 'user_id': user_id})

        general = get_config().app.general
        timezone_str = user_timezone or general.timezone
        freeze_time = calculate_freeze_time(freeze_option, general, timezone_str)
        await self.fetch_and_assign_user_name(incident_, user_id, dump=False)
        cached_user = self.users.get_user_by_id(user_id)
        await self.apply_time_freeze(incident_, freeze_time, cached_user, queue_, source=FreezeSource.TIME)
        await self.post_freeze_notification(incident_, ui_user=ui_user)

    def _handle_task_action(self, incident_, user_id, queue_):
        logger.info(log_button_pressed, extra={'uniq_id': incident_.uniq_id, 'button': 'task', 'user_id': user_id})
        self.track_async_task(asyncio.create_task(self.handle_task_button(incident_, queue_)))

    async def _handle_unfreeze_action(self, incident_: 'Incident', user_id: str, queue_: 'AsyncQueue'):
        if not incident_.can_manual_unfreeze():
            return
        logger.info(log_button_pressed, extra={'uniq_id': incident_.uniq_id, 'button': 'unfreeze', 'user_id': user_id})
        await queue_.delete_by_id_and_type(incident_.uniq_id, QueueItemType.UNFREEZE)
        await unfreeze_incident(incident_, queue_)
        await self.update_incident_message(incident_)

    def _load_stored_users(self, user_store, messenger_type: str) -> dict:
        stored_users = user_store.get_all_users_by_type(messenger_type)
        result = {}
        for user_id, stored_data in stored_users.items():
            result[user_id] = {
                'id': user_id,
                'exists': True,
                'full_name': stored_data.get('full_name'),
                'username': stored_data.get('username'),
                'email': stored_data.get('email'),
                'timezone': stored_data.get('timezone'),
            }
        if result:
            logger.info(f'Loaded {len(result)} users from storage')
        return result

    def _setup_http(self) -> RateLimitedClient:
        env = get_environment_config()
        rate_limit = self.provider.descriptor.rate_limit
        rate_window = self.provider.descriptor.rate_window_seconds
        if env.dev_messenger_rate_limit is not None:
            rate_limit = env.dev_messenger_rate_limit if env.dev_messenger_rate_limit > 0 else None
        if env.dev_messenger_rate_window is not None:
            rate_window = env.dev_messenger_rate_window

        if rate_limit:
            logger.debug(
                f"Rate limit: "
                f"{rate_limit} requests per {rate_window}s", extra={'messenger': self.type}
            )
        else:
            logger.info(f"{self.type.capitalize()} rate limiting disabled")

        client = RateLimitedClient(
            rate_limit=rate_limit,
            rate_window=rate_window,
            retry_attempts=3,
            timeout=30.0,
            connector_limit=100,
            connector_limit_per_host=30,
            redact_url=getattr(self.provider, 'redact_url', redact_messenger_url),
        )
        client.initialize_client()
        return client
