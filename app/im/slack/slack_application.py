import asyncio
import re

from fastapi.responses import JSONResponse

from app.config.config import get_config
from app.config.environment import get_environment_config
from app.config.validation import ApplicationConfig
from app.im.application import Application
from app.im.slack import reformat_message
from app.im.slack.config import slack_env, slack_admins_template_string
from app.im.slack.threads import slack_get_create_thread_payload, slack_get_update_payload
from app.im.slack.user import User
from app.logging import logger


class SlackApplication(Application):

    def __init__(self, app_config: ApplicationConfig, channels, default_channel):
        super().__init__(app_config, channels, default_channel)

    def _initialize_specific_params(self):
        self.post_message_url = f'{self.url}/api/chat.postMessage'
        env_config = get_environment_config()
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {env_config.slack_bot_user_oauth_token}',
        }
        self.rate_limit = 10
        self.thread_id_key = 'ts'

    def _get_url(self, app_config: ApplicationConfig):
        return 'https://slack.com'

    async def _get_public_url(self, app_config: ApplicationConfig):
        response = await self.http.get(
            'https://slack.com/api/auth.test',
            headers=self.headers
        )
        json_ = await response.json()
        response.close()
        return json_.get('url')

    def _get_team_name(self, app_config: ApplicationConfig):
        return None

    async def get_user_details(self, user_details):
        id_ = user_details.get('id')
        response = await self.http.get(f'{self.url}/api/users.info?user={id_}', headers=self.headers)
        if response.status != 200:
            logger.debug("User details fetch failed", extra={'user_id': id_, 'status': response.status})
            response.close()
            return {'id': id_, 'exists': False, 'full_name': None, 'username': None,
                    'first_name': None, 'last_name': None, 'email': None, 'timezone': None}

        data = await response.json()
        response.close()
        if not data.get('ok'):
            logger.debug("Slack API error", extra={'user_id': id_, 'error': data.get("error", "unknown error")})
            return {'id': id_, 'exists': False, 'full_name': None, 'username': None,
                    'first_name': None, 'last_name': None, 'email': None, 'timezone': None}

        user_data = data.get('user', {})
        profile = user_data.get('profile', {})
        full_name = profile.get('real_name_normalized')
        first_name = profile.get('first_name', '').strip()
        last_name = profile.get('last_name', '').strip()
        return {
            'id': id_,
            'exists': True,
            'full_name': full_name,
            'username': user_data.get('name'),
            'first_name': first_name or None,
            'last_name': last_name or None,
            'email': profile.get('email') or None,
            'timezone': user_data.get('tz') or None,
        }

    def create_user(self, name, user_details):
        return User(
            name=name,
            id_=user_details.get('id'),
            exists=user_details.get('exists'),
            timezone=user_details.get('timezone')
        )

    async def get_all_groups(self):
        """Fetch all user groups from Slack API using usergroups.list"""
        response = await self.http.get(f'{self.url}/api/usergroups.list', headers=self.headers)
        try:
            if response.status != 200:
                logger.debug(f'Failed to get groups list: HTTP {response.status}')
                return {}
            
            data = await response.json()
            if not data.get('ok'):
                logger.debug(f'Slack API error getting groups list: {data.get("error", "unknown error")}')
                return {}
            
            # Return a dict mapping group IDs to their names
            usergroups = data.get('usergroups', [])
            return {ug.get('id'): ug.get('name') for ug in usergroups if ug.get('id')}
        finally:
            response.close()

    async def _generate_groups(self, groups_dict):
        """Generate groups by polling them from the API"""
        if not groups_dict:
            return {}
        
        logger.info('Creating groups')
        
        # Get all groups from API once
        all_groups = await self.get_all_groups()

        groups = {}
        for config_name, group_info in groups_dict.items():
            group_name = all_groups.get(group_info.id)
            group_exists = group_name is not None
            group_details = {'id': group_info.id, 'name': group_name, 'exists': group_exists}
            if not group_exists:
                logger.warning('Group not found in Slack', extra={'group': config_name})
                group_details = {'id': None, 'name': None, 'exists': False}
            groups[config_name] = self.create_group(config_name, group_details)

        return groups

    def get_notification_destinations(self):
        return [a.get_notification_identifier() for a in self.admin_users]

    def get_admins_text(self):
        admins_text = slack_env.from_string(slack_admins_template_string).render(
            users=self.get_notification_destinations()
        )
        return admins_text

    async def _handle_chain_action(self, incident_, user_id, user_name, queue_):
        """Handle chain-related button actions"""
        await queue_.delete_by_id(incident_.uniq_id, delete_steps=True, delete_status=False)
        if incident_.chain_enabled or incident_.status != 'resolved':
            if incident_.assigned_user_id == user_id:
                logger.info('Button pressed: user already assigned', extra={'incident': incident_.uuid, 'button': 'take_it', 'user_id': user_id})
            else:
                logger.info('Button pressed: assigning to user', extra={'incident': incident_.uuid, 'button': 'take_it', 'user_id': user_id})
                incident_.assign_user_id(user_id)
                if user_name:
                    incident_.assign_user(user_name)
                self._track_async_task(asyncio.create_task(self.post_assignment_notification(incident_, user_id, user_name)))
                self._track_async_task(asyncio.create_task(self.fetch_and_assign_user_name(incident_, user_id)))
            incident_.chain_enabled = False
        else:
            logger.info('Button pressed', extra={'incident': incident_.uuid, 'button': 'release', 'user_id': user_id})
            self._track_async_task(asyncio.create_task(self.post_unassignment_notification(incident_)))
            incident_.release()

    def _build_button_response(self, incident_, original_message, user_id: str = None):
        """Build JSON response with updated incident message"""
        incident_.dump()
        body = self.body_template.form_message(incident_.payload, incident_)
        header = self.header_template.form_message(incident_.payload, incident_)
        status_icons = self.status_icons_template.form_message(incident_.payload, incident_)
        payload = self.update_thread_payload(incident_.channel_id, incident_.ts, body, header, status_icons,
                                             incident_.status, incident_.chain_enabled, incident_.frozen_until, 
                                             incident_.task_link)
        self._track_async_task(asyncio.create_task(self._update_thread(incident_.ts, payload)))
        user_tz = self._get_user_timezone(user_id)
        modified_message = reformat_message(original_message, payload['text'], payload['attachments'], incident_.status,
                                            incident_.chain_enabled, incident_.frozen_until, incident_.task_link, user_tz)
        return JSONResponse(modified_message, status_code=200)

    async def _handle_freeze_button(self, action, incident_, user_id, incidents, queue_):
        """Handle freeze button action"""
        if incident_.is_frozen():
            await self._handle_unfreeze_action(incident_, user_id, queue_)
            return
        
        if action.get('type') != 'select':
            return
        
        selected_options = action.get('selected_options', [])
        if not selected_options:
            return
        
        freeze_option = selected_options[0]['value']
        user_tz = self._get_user_timezone(user_id)
        await self._handle_freeze_action(incident_, freeze_option, user_id, incidents, queue_, user_timezone=user_tz)

    async def buttons_handler(self, payload, incidents, queue_, route):
        env_config = get_environment_config()
        if payload.get('token') != env_config.slack_verification_token:
            logger.error('Unauthorized request')
            return JSONResponse({}, status_code=401)

        incident_ = incidents.get_by_ts(ts=payload['message_ts'])
        original_message = payload.get('original_message')
        if incident_ is None:
            return JSONResponse(original_message, status_code=200)
        
        actions = payload.get('actions')
        user_id = payload.get('user')['id']
        user_name = self.get_configured_user_name(user_id, payload.get('user', {}).get('name'))

        # Check if this is a freeze action
        is_freeze_action = any(action['name'] == 'freeze' for action in actions)

        # Block non-freeze actions if incident is frozen
        if incident_.is_frozen() and not is_freeze_action:
            logger.debug('Incident frozen, blocking actions', extra={'incident': incident_.uuid})
            return self._build_button_response(incident_, original_message, user_id)

        # Handle freeze actions
        for action in actions:
            if action['name'] == 'freeze':
                await self._handle_freeze_button(action, incident_, user_id, incidents, queue_)
                return self._build_button_response(incident_, original_message, user_id)

        # Handle other actions
        for action in actions:
            if action['name'] == 'chain':
                await self._handle_chain_action(incident_, user_id, user_name, queue_)
            elif action['name'] == 'task':
                self._handle_task_action(incident_, user_id, queue_)
        
        return self._build_button_response(incident_, original_message, user_id)

    def _create_thread_payload(self, channel_id, body, header, status_icons, status):
        return slack_get_create_thread_payload(channel_id, body, header, status_icons, status)

    def _post_thread_payload(self, channel_id, id_, text):
        return {'channel': channel_id, 'thread_ts': id_, 'text': text, 'unfurl_links': False, 'unfurl_media': False}

    def update_thread_payload(self, channel_id, id_, body, header, status_icons, status, chain_enabled,
                              frozen_until, task_link=''):
        return slack_get_update_payload(channel_id, id_, body, header, status_icons, status, chain_enabled,
                                        frozen_until, task_link)

    async def _update_thread(self, id_, payload):
        response = await self.http.post(
            f'{self.url}/api/chat.update',
            headers=self.headers,
            json=payload
        )
        response.close()

    def _markdown_links_to_native_format(self, text):
        def replace_link(match):
            link_text = match.group(1)
            url = match.group(2)
            return f'<{url}|{link_text}>'

        pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        converted_text = re.sub(pattern, replace_link, text, flags=re.DOTALL)
        return converted_text
