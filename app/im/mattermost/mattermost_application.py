import asyncio

from fastapi.responses import JSONResponse

from app.config.config import get_config
from app.config.environment import get_environment_config
from app.config.validation import ApplicationConfig
from app.im.application import Application
from app.im.mattermost.config import (mattermost_env,
                                      mattermost_admins_template_string)
from app.im.mattermost.threads import mattermost_get_create_thread_payload, mattermost_get_update_payload, \
    mattermost_get_button_update_payload
from app.im.mattermost.user import User
from app.logging import logger


class MattermostApplication(Application):

    def __init__(self, app_config: ApplicationConfig, channels, default_channel):
        super().__init__(app_config, channels, default_channel)

    def _initialize_specific_params(self):
        self.post_message_url = f'{self.url}/api/v4/posts'
        env_config = get_environment_config()
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {env_config.mattermost_access_token}',
        }
        self.rate_limit = 10
        self.thread_id_key = 'id'

    def _get_url(self, app_config: ApplicationConfig):
        return app_config.address

    def _get_public_url(self, app_config: ApplicationConfig):
        return app_config.address

    def _get_team_name(self, app_config: ApplicationConfig):
        return app_config.team

    async def get_user_details(self, user_details):
        id_ = user_details.get('id')
        response = await self.http.get(f'{self.url}/api/v4/users/{id_}?user_id={id_}', headers=self.headers)

        if response.status == 404:
            logger.debug("User not found", extra={'user_id': id_})
            response.close()
            return {'id': id_, 'username': None, 'exists': False, 'full_name': None,
                    'first_name': None, 'last_name': None, 'email': None, 'timezone': None}

        if response.status != 200:
            logger.debug("User details fetch failed", extra={'user_id': id_, 'status': response.status})
            response.close()
            return {'id': id_, 'username': None, 'exists': False, 'full_name': None,
                    'first_name': None, 'last_name': None, 'email': None, 'timezone': None}

        data = await response.json()
        response.close()
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        full_name = f"{first_name} {last_name}".strip()
        return {
            'id': id_,
            'username': data.get('username'),
            'exists': True,
            'full_name': full_name,
            'first_name': first_name or None,
            'last_name': last_name or None,
            'email': data.get('email') or None,
            'timezone': data.get('timezone') or None,
        }

    def create_user(self, name, user_details):
        return User(
            name=name,
            id_=user_details.get('id'),
            username=user_details.get('username'),
            exists=user_details.get('exists')
        )

    async def get_group_details(self, group_id: str):
        """Fetch a single group from Mattermost API using /api/v4/groups/<group_id>"""
        if not group_id:
            return {'id': None, 'name': None, 'exists': False}
        
        try:
            response = await self.http.get(
                f'{self.url}/api/v4/groups/{group_id}',
                headers=self.headers
            )
            try:
                if response.status == 404:
                    logger.debug("Group not found", extra={'group_id': group_id})
                    return {'id': group_id, 'name': None, 'exists': False}
                
                if response.status != 200:
                    logger.debug("Group details fetch failed", extra={'group_id': group_id, 'status': response.status})
                    return {'id': group_id, 'name': None, 'exists': False}
                
                data = await response.json()
                group_name = data.get('name')
                return {'id': group_id, 'name': group_name, 'exists': True}
            finally:
                response.close()
        except Exception as e:
            logger.error("Group details fetch error", extra={'group_id': group_id, 'error': str(e)})
            return {'id': group_id, 'name': None, 'exists': False}

    async def _generate_groups(self, groups_dict):
        """Generate groups by checking each group individually via API"""
        if not groups_dict:
            return {}
        
        logger.info('Creating groups')
        
        groups = {}
        for config_name, group_info in groups_dict.items():
            group_details = await self.get_group_details(group_info.id)
            if not group_details['exists']:
                logger.warning('Group not found in Mattermost', extra={'group_id': group_info.id, 'group_name': config_name})
                group_details = {'id': None, 'name': None, 'exists': False}
            groups[config_name] = self.create_group(config_name, group_details)

        return groups

    async def get_all_groups(self):
        """Unused function for Mattermost"""
        return {}

    def get_notification_destinations(self):
        return [a.get_notification_identifier() for a in self.admin_users]

    def get_admins_text(self):
        admins_text = mattermost_env.from_string(mattermost_admins_template_string).render(
            users=self.get_notification_destinations()
        )
        return admins_text

    async def _handle_chain_action(self, incident_, user_id, user_name, queue_, incidents, payload):
        """Handle chain-related button actions"""
        await queue_.delete_by_id(incident_.uniq_id, delete_steps=True, delete_status=False)
        if incident_.chain_enabled or incident_.status != 'resolved':
            if incident_.assigned_user_id == user_id:
                logger.info('Button pressed. User already assigned', extra={'incident': incident_.uuid, 'button': 'take_it', 'user_id': user_id})
                return JSONResponse(payload, status_code=200)
            logger.info('Button pressed: assigning to user', extra={'incident': incident_.uuid, 'button': 'take_it', 'user_id': user_id})
            incident_.assign_user_id(user_id)
            incident_.assign_user(user_name)
            self._track_async_task(asyncio.create_task(self.post_assignment_notification(incident_, user_id, user_name)))
            self._track_async_task(asyncio.create_task(self.fetch_and_assign_user_name(incident_, user_id, incidents)))
            incident_.chain_enabled = False
        else:
            logger.info('Button pressed', extra={'uuid': incident_.uuid, 'button': 'release', 'user_id': user_id})
            self._track_async_task(asyncio.create_task(self.post_unassignment_notification(incident_)))
            incident_.release()
        return None

    def _build_button_response(self, incident_, user_timezone='UTC'):
        """Build JSON response with updated incident message"""
        incident_.dump()
        status_icons = self.status_icons_template.form_message(incident_.payload, incident_)
        header = self.header_template.form_message(incident_.payload, incident_)
        message = self.body_template.form_message(incident_.payload, incident_)
        response_payload = mattermost_get_button_update_payload(
            message, header, status_icons, incident_.status,
            incident_.chain_enabled, incident_.frozen_until, incident_.task_link, user_timezone)
        return JSONResponse(response_payload, status_code=200)

    async def buttons_handler(self, payload, incidents, queue_, route):
        post_id = payload['post_id']
        incident_ = incidents.get_by_ts(ts=post_id)
        if incident_ is None:
            return JSONResponse(payload, status_code=200)
        
        context = payload.get('context', {})
        user_id = payload.get('user_id')
        user_name = self.get_configured_user_name(user_id, payload.get('user_name'))
        
        config = get_config()
        mattermost_tz = config.app.general.timezone

        # Handle freeze/unfreeze actions first
        selected_option = context.get('selected_option')
        if selected_option and selected_option.startswith('freeze_'):
            freeze_option = selected_option.replace('freeze_', '')
            await self._handle_freeze_action(incident_, freeze_option, user_id, incidents, queue_, user_name, user_timezone=mattermost_tz)
        else:
            action = context.get('action')
            if action == 'unfreeze':
                await self._handle_unfreeze_action(incident_, user_id, queue_)

        # Block other actions if incident is frozen
        if incident_.is_frozen():
            logger.debug('Incident frozen, blocking actions', extra={'uuid': incident_.uuid})
            return self._build_button_response(incident_, mattermost_tz)

        # Handle other button actions
        action = context.get('action')
        if action == 'chain':
            early_return = await self._handle_chain_action(incident_, user_id, user_name, queue_, incidents, payload)
            if early_return is not None:
                return early_return
        elif action == 'task':
            self._handle_task_action(incident_, user_id, queue_)
        
        return self._build_button_response(incident_, mattermost_tz)

    def _create_thread_payload(self, channel_id, body, header, status_icons, status):
        return mattermost_get_create_thread_payload(channel_id, body, header, status_icons, status)

    def _post_thread_payload(self, channel_id, id_, text):
        return {'channel_id': channel_id, 'root_id': id_, 'message': text}

    def update_thread_payload(self, channel_id, id_, body, header, status_icons, status, chain_enabled,
                              frozen_until, task_link=''):
        return mattermost_get_update_payload(channel_id, id_, body, header, status_icons, status, chain_enabled,
                                             frozen_until, task_link)

    async def _update_thread(self, id_, payload):
        response = await self.http.put(
            f'{self.url}/api/v4/posts/{id_}',
            headers=self.headers,
            json=payload
        )
        response.close()

    def _markdown_links_to_native_format(self, text):
        return text
