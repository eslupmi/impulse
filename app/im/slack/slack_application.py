import asyncio

from fastapi.responses import JSONResponse

from app.config.environment import get_environment_config
from app.config.validation import ApplicationConfig
from app.im.application import Application
from app.im.slack.threads import slack_get_update_payload
from app.im.slack.user import User
from app.logging import logger


from app.im.providers.slack import SlackProvider


class SlackApplication(SlackProvider, Application):
    """Legacy callback/user adapter; startup uses the composed Application."""

    def __init__(self, app_config: ApplicationConfig, channels, default_channel, webhooks=None):
        Application.__init__(self, app_config, channels, default_channel, webhooks=webhooks)

    def create_user(self, name, user_details):
        return User(
            name=name,
            id_=user_details.get('id'),
            exists=user_details.get('exists'),
            full_name=user_details.get('full_name'),
            username=user_details.get('username'),
            email=user_details.get('email'),
            timezone_=user_details.get('timezone')
        )

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
        if incident_.is_frozen and (incident_.frozen_by_inhibition or not is_freeze_action):
            logger.debug('Incident frozen, blocking actions', extra={'incident': incident_.uniq_id})
            return JSONResponse(original_message, status_code=200)
        else:
            user_tz = self._get_user_timezone_str(user_id)
            for action in actions:
                if action['name'] == 'freeze':
                    await self._handle_freeze_button(action, incident_, user_id, incidents, queue_, user_tz)
                if action['name'] == 'chain':
                    await self._handle_chain_action(incident_, user_id, queue_)
                elif action['name'] == 'task':
                    self._handle_task_action(incident_, user_id, queue_)
            return self._build_button_response(incident_, user_tz)

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
            if not group_exists:
                logger.warning('Group not found in Slack', extra={'group': config_name})
            groups[config_name] = self.create_group(config_name, {
                'id': group_info.id,
                'name': group_name,
                'exists': group_exists,
            })

        return groups

    def _build_button_response(self, incident_, user_tz='UTC'):
        incident_.dump()
        body, header, status_icons = self.form_body_header_status_icons(incident_)
        response_payload = slack_get_update_payload(incident_, body, header, status_icons, user_tz)
        return JSONResponse(response_payload, status_code=200)

    async def _handle_chain_action(self, incident_, user_id, queue_):
        """Handle chain-related button actions"""
        await queue_.delete_by_id(incident_.uniq_id, delete_steps=True, delete_status=False)
        if incident_.chain_enabled or incident_.status != 'resolved':
            if incident_.assigned_user_id == user_id:
                logger.info('Button pressed: user already assigned', extra={'incident': incident_.uniq_id, 'button': 'take_it', 'user_id': user_id})
            else:
                logger.info('Button pressed: assigning to user', extra={'incident': incident_.uniq_id, 'button': 'take_it', 'user_id': user_id})
                self.fetch_and_assign_user_name(incident_, user_id, dump=False)
                self.track_async_task(asyncio.create_task(self.post_assignment_notification(incident_)))
            incident_.chain_enabled = False
        else:
            logger.info('Button pressed', extra={'incident': incident_.uniq_id, 'button': 'release', 'user_id': user_id})
            self.track_async_task(asyncio.create_task(self.post_unassignment_notification(incident_)))
            incident_.release()

    async def _handle_freeze_button(self, action, incident_, user_id, incidents, queue_, tz_str):
        """Handle freeze button action"""
        if incident_.can_manual_unfreeze():
            await self._handle_unfreeze_action(incident_, user_id, queue_)
            return

        if action.get('type') != 'select':
            return

        selected_options = action.get('selected_options', [])
        if not selected_options:
            return

        freeze_option = selected_options[0]['value']
        await self._handle_freeze_action(incident_, freeze_option, user_id, incidents, queue_, user_timezone=tz_str)
