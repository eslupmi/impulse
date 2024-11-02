import json
import re
from time import sleep

import requests

from app.im.application import Application
from app.im.colors import status_colors
from app.im.exceptions import UserGenerationError
from app.im.slack import reformat_message
from app.im.slack.config import slack_headers, slack_request_delay, slack_bold_text, slack_env, \
    slack_admins_template_string
from app.im.slack.threads import slack_get_create_thread_payload, slack_get_update_payload
from app.im.slack.user import User
from app.logging import logger
from config import slack_verification_token


class SlackApplication(Application):

    def __init__(self, app_config, channels_list, default_channel):
        super().__init__(app_config, channels_list, default_channel)

    def _initialize_specific_params(self):
        self.post_message_url = f'{self.url}/api/chat.postMessage'
        self.headers = slack_headers
        self.post_delay = slack_request_delay
        self.thread_id_key = 'ts'

    def _get_public_channels(self) -> dict:
        try:
            response = self.http.get(
                f'{self.url}/api/conversations.list',
                params={'limit': 1000},
                headers=self.headers
            )
            response.raise_for_status()
            sleep(self.post_delay)
            return {c.get('name'): c for c in response.json().get('channels', [])}
        except requests.exceptions.RequestException as e:
            logger.error(f'Failed to retrieve public channels list: {e}')
            return {}

    def _get_private_channels(self) -> dict:
        try:
            response = self.http.get(
                f'{self.url}/api/conversations.list',
                params={'types': 'private_channel', 'limit': 1000},
                headers=self.headers
            )
            response.raise_for_status()
            sleep(self.post_delay)
            return {c.get('name'): c for c in response.json().get('channels', [])}
        except requests.exceptions.RequestException as e:
            logger.error(f'Failed to retrieve private channels list: {e}')
            return {}

    def _get_url(self, app_config):
        return 'https://slack.com'

    def _get_public_url(self, app_config):
        response = self.http.get(
            f'https://slack.com/api/auth.test',
            headers=slack_headers
        )
        sleep(slack_request_delay)
        json_ = response.json()
        return json_.get('url')

    def _get_team_name(self, app_config):
        return None

    def get_user_details(self, s_users, user_info):
        full_name = user_info['full_name']
        user = next((u for u in s_users if u.get('real_name') == full_name), None)
        if user:
            return {
                'name': user_info.get('full_name'),
                'id': user.get('id')
            }
        logger.warning(f"User '{full_name}' not found in Slack")
        return {'name': user_info.get('name')}

    def _get_users(self, users):
        full_names = [u['full_name'] for k, u in users.items()]
        filtered_users = []
        request_data = {
            'limit': 50,
        }
        logger.info(f'Get users from Slack')
        try:
            while len(filtered_users) < len(full_names):
                response = self.http.get(
                    f'{self.url}/api/users.list',
                    params=request_data,
                    headers=self.headers
                )
                response.raise_for_status()
                sleep(slack_request_delay)
                json_data = response.json()
                for user in json_data.get('members', []):
                    if user.get('real_name') in full_names:
                        filtered_users.append(user)
                cursor = json_data.get('response_metadata', {}).get('next_cursor')
                request_data.update({'cursor': cursor})
                if not cursor:
                    break
            return filtered_users
        except requests.exceptions.RequestException as e:
            logger.error(f'Incorrect Slack response. Reason: {e}')
            raise UserGenerationError(f'Failed to retrieve users: {e}')

    def create_user(self, name, user_details):
        # Create an instance of the Slack User
        return User(
            name=name,
            slack_id=user_details.get('id')
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

    def send_message(self, channel_id, text, attachment):
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
        response = self.http.post(f'{self.url}/api/chat.postMessage', headers=self.headers, data=json.dumps(payload))
        sleep(self.post_delay)
        return response.json().get('ts')

    def buttons_handler(self, payload, incidents, queue_):
        if payload.get('token') != slack_verification_token:
            logger.error(f'Unauthorized request to \'/slack\'')
            return {}, 401

        incident_ = incidents.get_by_ts(ts=payload['message_ts'])
        original_message = payload.get('original_message')
        if incident_ is None:
            return original_message, 200
        actions = payload.get('actions')

        for action in actions:
            if action['name'] == 'chain':
                if incident_.chain_enabled:
                    incident_.chain_enabled = False
                    queue_.delete_by_id(incident_.uuid, delete_steps=True, delete_status=False)
                else:
                    incident_.chain_enabled = True
                    queue_.recreate(incident_.uuid, incident_.chain)
            elif action['name'] == 'status':
                if incident_.status_enabled:
                    incident_.status_enabled = False
                else:
                    incident_.status_enabled = True
        incident_.dump()
        modified_message = reformat_message(original_message, incident_.chain_enabled, incident_.status_enabled)
        return modified_message, 200

    def _create_thread_payload(self, channel_id, body, header, status_icons, status):
        return slack_get_create_thread_payload(channel_id, body, header, status_icons, status)

    def _post_thread_payload(self, channel_id, id_, text):
        return {'channel': channel_id, 'thread_ts': id_, 'text': text, 'unfurl_links': False, 'unfurl_media': False}

    def _update_thread_payload(self, channel_id, id_, body, header, status_icons, status, chain_enabled,
                               status_enabled):
        return slack_get_update_payload(channel_id, id_, body, header, status_icons, status, chain_enabled,
                                        status_enabled)

    def _update_thread(self, id_, payload):
        requests.post(
            f'{self.url}/api/chat.update',
            headers=slack_headers,
            data=json.dumps(payload)
        )

    def _markdown_links_to_native_format(self, text):
        def replace_link(match):
            link_text = match.group(1)
            url = match.group(2)
            return f'<{url}|{link_text}>'

        pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        converted_text = re.sub(pattern, replace_link, text, flags=re.DOTALL)
        return converted_text
