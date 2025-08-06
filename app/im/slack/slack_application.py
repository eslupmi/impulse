import asyncio
import re

import aiohttp
from fastapi.responses import JSONResponse

from app.im.application import Application
from app.im.colors import status_colors
from app.im.slack import reformat_message
from app.im.slack.config import slack_headers, slack_request_delay, slack_bold_text, slack_env, \
    slack_admins_template_string
from app.im.slack.threads import slack_get_create_thread_payload, slack_get_update_payload
from app.im.slack.user import User
from app.logging import logger
from config import slack_verification_token


class SlackApplication(Application):

    def __init__(self, app_config, channels, default_channel):
        super().__init__(app_config, channels, default_channel)

    def _initialize_specific_params(self):
        self.post_message_url = f'{self.url}/api/chat.postMessage'
        self.headers = slack_headers
        self.post_delay = slack_request_delay
        self.thread_id_key = 'ts'

    def _get_url(self, app_config):
        return 'https://slack.com'

    async def _get_public_url(self, app_config):
        async with self.http.get(
            f'https://slack.com/api/auth.test',
            headers=slack_headers
        ) as response:
            await asyncio.sleep(slack_request_delay)
            json_ = await response.json()
            return json_.get('url')

    def _get_team_name(self, app_config):
        return None

    async def get_user_details(self, user_details):
        id_ = user_details.get('id')
        async with self.http.get(f'{self.url}/api/users.info?user={id_}', headers=self.headers) as response:
            if response.status != 200:
                logger.debug(f'Failed to get user details for {id_}: HTTP {response.status}')
                return {'id': id_, 'exists': False, 'full_name': None, 'username': None}
            
            data = await response.json()
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

    def format_text_bold(self, text):
        return slack_bold_text(text)

    def format_text_italic(self, text):
        return f'_{text}_'

    def _format_text_link(self, text, url):
        return f"(<{url}|{text}>)"

    def get_admins_text(self):
        admins_text = slack_env.from_string(slack_admins_template_string).render(
            users=self.get_notification_destinations()
        )
        return admins_text

    async def send_message(self, channel_id, text, attachment):
        payload = {
            'channel': channel_id,
            'text': text,
            'unfurl_links': False,
            'unfurl_media': False,
            'attachments': [
                {
                    'color': status_colors['closed'],
                    'text': attachment,
                    'mrkdwn_in': ['text'],
                }
            ]
        }
        async with self.http.post(f'{self.url}/api/chat.postMessage', headers=self.headers, json=payload) as response:
            await asyncio.sleep(self.post_delay)
            response_json = await response.json()
            return response_json.get('ts')

    async def buttons_handler(self, payload, incidents, queue_, route):
        if payload.get('token') != slack_verification_token:
            logger.error(f'Unauthorized request to \'/slack\'')
            return JSONResponse({}, status_code=401)

        incident_ = incidents.get_by_ts(ts=payload['message_ts'])
        original_message = payload.get('original_message')
        if incident_ is None:
            return JSONResponse(original_message, status_code=200)
        actions = payload.get('actions')

        user_id = payload.get('user')['id']

        for action in actions:
            if action['name'] == 'chain':
                await queue_.delete_by_id(incident_.uuid, delete_steps=True, delete_status=False)
                if incident_.chain_enabled or incident_.status != 'resolved':
                    logger.info(f'Incident {incident_.uuid} -> button TAKE IT pressed')
                    incident_.assign_user_id(user_id)
                    asyncio.create_task(self.fetch_and_assign_user_name(incident_, user_id, incidents))
                    incident_.chain_enabled = False
                else:
                    logger.info(f'Incident {incident_.uuid} -> button RELEASE pressed')
                    incident_.release()
            elif action['name'] == 'status':
                if incident_.status_enabled:
                    logger.info(f'Incident {incident_.uuid} -> button STATUS pressed (disabled)')
                    incident_.status_enabled = False
                else:
                    logger.info(f'Incident {incident_.uuid} -> button STATUS pressed (enabled)')
                    incident_.status_enabled = True
        incident_.dump()

        body = self.body_template.form_message(incident_.last_state, incident_)
        header = self.header_template.form_message(incident_.last_state, incident_)
        status_icons = self.status_icons_template.form_message(incident_.last_state, incident_)
        payload = self.update_thread_payload(incident_.channel_id, incident_.ts, body, header, status_icons,
                                             incident_.status, incident_.chain_enabled, incident_.status_enabled)
        modified_message = reformat_message(original_message, payload['text'], payload['attachments'], incident_.status,
                                            incident_.chain_enabled, incident_.status_enabled)
        return JSONResponse(modified_message, status_code=200)

    def _create_thread_payload(self, channel_id, body, header, status_icons, status):
        return slack_get_create_thread_payload(channel_id, body, header, status_icons, status)

    def _post_thread_payload(self, channel_id, id_, text):
        return {'channel': channel_id, 'thread_ts': id_, 'text': text, 'unfurl_links': False, 'unfurl_media': False}

    def update_thread_payload(self, channel_id, id_, body, header, status_icons, status, chain_enabled,
                              status_enabled):
        return slack_get_update_payload(channel_id, id_, body, header, status_icons, status, chain_enabled,
                                        status_enabled)

    async def _update_thread(self, id_, payload):
        async with self.http.post(
            f'{self.url}/api/chat.update',
            headers=slack_headers,
            json=payload
        ) as response:
            await asyncio.sleep(self.post_delay)

    def _markdown_links_to_native_format(self, text):
        def replace_link(match):
            link_text = match.group(1)
            url = match.group(2)
            return f'<{url}|{link_text}>'

        pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        converted_text = re.sub(pattern, replace_link, text, flags=re.DOTALL)
        return converted_text
