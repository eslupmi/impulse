import asyncio
import re
from datetime import datetime

from fastapi.responses import JSONResponse

from app.im.application import Application
from app.im.slack import reformat_message
from app.im.slack.config import slack_env, slack_admins_template_string
from app.im.slack.threads import slack_get_create_thread_payload, slack_get_update_payload
from app.im.slack.user import User
from app.im.template import notification_freeze, notification_unfreeze
from app.jinja_template import JinjaTemplate
from app.logging import logger
from app.config.config import get_config
from app.config.validation import ApplicationConfig
from app.time import calculate_freeze_time, format_freeze_expiration
from app.queue.queue import AsyncQueue
from app.queue.constants import QueueItemType
from app.incident.incident import Incident


class SlackApplication(Application):

    def __init__(self, app_config: ApplicationConfig, channels, default_channel):
        super().__init__(app_config, channels, default_channel)

    def _initialize_specific_params(self):
        self.post_message_url = f'{self.url}/api/chat.postMessage'
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {get_config().slack_bot_user_oauth_token}',
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
            logger.debug(f'Failed to get user details for {id_}: HTTP {response.status}')
            response.close()
            return {'id': id_, 'exists': False, 'full_name': None, 'username': None}

        data = await response.json()
        response.close()
        if not data.get('ok'):
            logger.debug(f'Slack API error for user {id_}: {data.get("error", "unknown error")}')
            return {'id': id_, 'exists': False, 'full_name': None, 'username': None}

        user_data = data.get('user', {})
        profile = user_data.get('profile', {})
        full_name = profile.get('real_name_normalized')
        return {'id': id_, 'exists': True, 'full_name': full_name}

    def create_user(self, name, user_details):
        return User(
            name=name,
            id_=user_details.get('id'),
            exists=user_details.get('exists')
        )

    def get_notification_destinations(self):
        return [a.id for a in self.admin_users]

    def get_admins_text(self):
        admins_text = slack_env.from_string(slack_admins_template_string).render(
            users=self.get_notification_destinations()
        )
        return admins_text

    async def _handle_chain_action(self, incident_, user_id, queue_, incidents):
        """Handle chain-related button actions"""
        await queue_.delete_by_id(incident_.uniq_id, delete_steps=True, delete_status=False)
        if incident_.chain_enabled or incident_.status != 'resolved':
            if incident_.assigned_user_id == user_id:
                logger.info(f'Incident {incident_.uuid} -> button TAKE IT pressed, but user is already assigned')
            else:
                logger.info(f'Incident {incident_.uuid} -> button TAKE IT pressed, assigning to {user_id}')
                incident_.assign_user_id(user_id)
                self._track_async_task(asyncio.create_task(self.post_assignment_notification(incident_, user_id)))
                self._track_async_task(asyncio.create_task(self.fetch_and_assign_user_name(incident_, user_id, incidents)))
            incident_.chain_enabled = False
        else:
            logger.info(f'Incident {incident_.uuid} -> button RELEASE pressed')
            self._track_async_task(asyncio.create_task(self.post_unassignment_notification(incident_)))
            incident_.release()

    async def _handle_freeze_action(self, incident_: Incident, freeze_option: str, user_id: str, incidents, queue_: AsyncQueue, user_display_name: str = None, user_timezone: str = "UTC"):
        """Handle freeze button action"""
        config = get_config()
        freeze_time = calculate_freeze_time(freeze_option, config.app.general, user_timezone)

        incident_.assign_user_id(user_id)
        await self.fetch_and_assign_user_name(incident_, user_id, incidents, dump=False)
        incident_.freeze(freeze_time, user_id)
        
        logger.info(f'Incident {incident_.uuid} -> FREEZE with option {freeze_option}, frozen until {freeze_time} (user timezone: {user_timezone})')
        
        await queue_.delete_by_id(incident_.uniq_id, delete_steps=True, delete_status=False)
        await queue_.put(freeze_time, QueueItemType.UNFREEZE, incident_.uniq_id)
        self._track_async_task(asyncio.create_task(self._post_freeze_notification(incident_, freeze_time, user_timezone)))

    async def _post_freeze_notification(self, incident_: Incident, freeze_time: datetime, user_timezone: str = "UTC"):
        """Post freeze notification to thread"""
        header = self.header_template.form_message(incident_.payload, incident_)
        text_template = JinjaTemplate(notification_freeze)
        fields = {'type': self.type.value, 'frozen_until': format_freeze_expiration(freeze_time, user_timezone)}
        text = text_template.form_notification(fields)
        message = header + '\n' + text
        await self.post_thread(incident_.channel_id, incident_.ts, message)

    async def _post_unfreeze_notification(self, incident_: Incident):
        """Post unfreeze notification to thread"""
        header = self.header_template.form_message(incident_.payload, incident_)
        text_template = JinjaTemplate(notification_unfreeze)
        text = text_template.form_notification({'type': self.type.value})
        message = header + '\n' + text
        await self.post_thread(incident_.channel_id, incident_.ts, message)

    def _build_button_response(self, incident_, original_message):
        """Build JSON response with updated incident message"""
        incident_.dump()
        body = self.body_template.form_message(incident_.payload, incident_)
        header = self.header_template.form_message(incident_.payload, incident_)
        status_icons = self.status_icons_template.form_message(incident_.payload, incident_)
        payload = self.update_thread_payload(incident_.channel_id, incident_.ts, body, header, status_icons,
                                             incident_.status, incident_.chain_enabled, incident_.frozen_until, 
                                             incident_.task_link)
        self._track_async_task(asyncio.create_task(self._update_thread(incident_.ts, payload)))
        config = get_config()
        slack_tz = config.messenger.timezone
        modified_message = reformat_message(original_message, payload['text'], payload['attachments'], incident_.status,
                                            incident_.chain_enabled, incident_.frozen_until, incident_.task_link, slack_tz)
        return JSONResponse(modified_message, status_code=200)

    async def buttons_handler(self, payload, incidents, queue_, route):
        config = get_config()
        if payload.get('token') != config.slack_verification_token:
            logger.error('Unauthorized request to \'/slack\'')
            return JSONResponse({}, status_code=401)

        incident_ = incidents.get_by_ts(ts=payload['message_ts'])
        original_message = payload.get('original_message')
        if incident_ is None:
            return JSONResponse(original_message, status_code=200)
        
        actions = payload.get('actions')
        user_id = payload.get('user')['id']
        is_freeze_action = any(action['name'] == 'freeze' for action in actions)

        if incident_.is_frozen() and not is_freeze_action:
            logger.info(f'Incident {incident_.uuid} is frozen, blocking all button actions')
            return self._build_button_response(incident_, original_message)

        for action in actions:
            if action['name'] == 'freeze':
                if incident_.is_frozen():
                    await self._handle_unfreeze_action(incident_, queue_)
                elif action.get('type') == 'select' and 'selected_options' in action and len(action['selected_options']) > 0:
                    freeze_option = action['selected_options'][0]['value']
                    config = get_config()
                    slack_tz = config.messenger.timezone
                    await self._handle_freeze_action(incident_, freeze_option, user_id, incidents, queue_, user_timezone=slack_tz)
                return self._build_button_response(incident_, original_message)

        for action in actions:
            if action['name'] == 'chain':
                await self._handle_chain_action(incident_, user_id, queue_, incidents)
            elif action['name'] == 'task':
                self._handle_task_action(incident_, queue_)
        
        return self._build_button_response(incident_, original_message)

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
