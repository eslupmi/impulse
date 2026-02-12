import asyncio
import re

from fastapi.responses import JSONResponse

from app.config.config import get_config
from app.config.environment import get_environment_config
from app.config.validation import ApplicationConfig
from app.im.application import Application
from app.im.slack.threads import get_incident_message_payload, slack_get_update_payload
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
        return {
            'id': id_,
            'exists': True,
            'full_name': profile.get('real_name_normalized'),
            'username': user_data.get('name'),
            'email': profile.get('email'),
            'timezone': user_data.get('tz'),
        }

    def create_user(self, name, user_details):
        return User(
            name=name,
            id_=user_details.get('id'),
            exists=user_details.get('exists'),
            full_name=user_details.get('full_name')
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

    async def _handle_chain_action(self, incident_, user_id, queue_):
        """Handle chain-related button actions"""
        await queue_.delete_by_id(incident_.uniq_id, delete_steps=True, delete_status=False)
        if incident_.chain_enabled or incident_.status != 'resolved':
            if incident_.assigned_user_id == user_id:
                logger.info('Button pressed: user already assigned', extra={'incident': incident_.uuid, 'button': 'take_it', 'user_id': user_id})
            else:
                logger.info('Button pressed: assigning to user', extra={'incident': incident_.uuid, 'button': 'take_it', 'user_id': user_id})
                self.fetch_and_assign_user_name(incident_, user_id)
                self.track_async_task(asyncio.create_task(self.post_assignment_notification(incident_)))
            incident_.chain_enabled = False
        else:
            logger.info('Button pressed', extra={'incident': incident_.uuid, 'button': 'release', 'user_id': user_id})
            self.track_async_task(asyncio.create_task(self.post_unassignment_notification(incident_)))
            incident_.release()

    async def _handle_freeze_button(self, action, incident_, user_id, incidents, queue_):
        """Handle freeze button action"""
        if incident_.frozen_until is not None:
            await self._handle_unfreeze_action(incident_, user_id, queue_)
            return
        
        if action.get('type') != 'select':
            return
        
        selected_options = action.get('selected_options', [])
        if not selected_options:
            return
        
        freeze_option = selected_options[0]['value']
        config = get_config()
        slack_tz = config.app.general.timezone
        await self._handle_freeze_action(incident_, freeze_option, user_id, incidents, queue_, user_timezone=slack_tz)

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

        # Check if this is a freeze action
        is_freeze_action = any(action['name'] == 'freeze' for action in actions)

        # Block non-freeze actions if incident is frozen
        if incident_.is_frozen() and (incident_.frozen_by_inhibition or not is_freeze_action):
            logger.debug('Incident frozen, blocking actions', extra={'incident': incident_.uuid})
            return JSONResponse(original_message, status_code=200)
        else:
            for action in actions:
                if action['name'] == 'freeze':
                    await self._handle_freeze_button(action, incident_, user_id, incidents, queue_)
                if action['name'] == 'chain':
                    self.fetch_and_assign_user_name(incident_, user_id)
                    await self._handle_chain_action(incident_, user_id, queue_)
                elif action['name'] == 'task':
                    self._handle_task_action(incident_, user_id, queue_)
            body, header, status_icons = self.form_body_header_status_icons(incident_)
            modified_message = slack_get_update_payload(incident_, body, header, status_icons)
            return JSONResponse(modified_message, status_code=200)

    def _get_incident_message_payload(self, incident, body, header, status_icons):
        return get_incident_message_payload(incident, body, header, status_icons)

    def _post_thread_payload(self, channel_id, id_, text):
        return {'channel': channel_id, 'thread_ts': id_, 'text': text, 'unfurl_links': False, 'unfurl_media': False}

    def update_incident_payload(self, incident, body, header, status_icons):
        return slack_get_update_payload(incident, body, header, status_icons)

    async def _update_incident_message(self, id_, payload):
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
