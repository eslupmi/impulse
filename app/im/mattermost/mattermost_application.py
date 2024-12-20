import json
from time import sleep

import requests

from app.im.application import Application
from app.im.colors import status_colors
from app.im.mattermost.config import (mattermost_headers, mattermost_request_delay, mattermost_bold_text,
                                      mattermost_env, mattermost_admins_template_string)
from app.im.mattermost.threads import mattermost_get_create_thread_payload, mattermost_get_update_payload
from app.im.mattermost.user import User
from app.logging import logger


class MattermostApplication(Application):

    def __init__(self, app_config, channels, default_channel):
        super().__init__(app_config, channels, default_channel)

    def _initialize_specific_params(self):
        self.post_message_url = f'{self.url}/api/v4/posts'
        self.headers = mattermost_headers
        self.post_delay = mattermost_request_delay
        self.thread_id_key = 'id'

    def _get_channels(self, team):
        try:
            response = self.http.get(
                f"{self.url}/api/v4/teams/{team['id']}/channels",
                params={'per_page': 1000},
                headers=self.headers
            )
            response.raise_for_status()
            sleep(self.post_delay)
            data = response.json()
            return {c.get('name'): c for c in data}
        except requests.exceptions.RequestException as e:
            logger.error(f'Failed to retrieve channel list: {e}')
            return {}

    def _get_url(self, app_config):
        return app_config['address']

    def _get_public_url(self, app_config):
        return app_config['address']

    def _get_team_name(self, app_config):
        logger.info(f'Get {self.type.capitalize()} team name')
        return app_config['team']

    def get_user_details(self, id_):
        if id_ is not None:
            response = self.http.get(f'{self.url}/api/v4/users/{id_}?user_id={id_}', headers=self.headers)
            data = response.json()
            if response.status_code == 404:
                exists = False
            else:
                exists = True
            return {'id': id_, 'username': data.get('username'), 'exists': exists}
        else:
            return {'id': None, 'username': None, 'exists': False}

    def create_user(self, name, user_details):
        return User(
            name=name,
            id_=user_details.get('id'),
            username=user_details.get('username'),
            exists=user_details.get('exists')
        )

    def get_notification_destinations(self):
        return [a.username for a in self.admin_users]

    def format_text_bold(self, text):
        return mattermost_bold_text(text)

    def format_text_italic(self, text):
        return f'_{text}_'

    def _format_text_link(self, text, url):
        return f"([{text}]({url}))"

    def get_admins_text(self):
        admins_text = mattermost_env.from_string(mattermost_admins_template_string).render(
            users=self.get_notification_destinations()
        )
        return admins_text

    def send_message(self, channel_id, text, attachment):
        payload = {
            'channel_id': channel_id,
            'message': text,
            'props': {
                'attachments': [
                    {
                        'fallback': 'test',
                        'text': attachment,
                        'color': status_colors['closed']
                    }
                ]
            }
        }
        response = self.http.post(f'{self.url}/api/v4/posts', headers=self.headers, data=json.dumps(payload))
        sleep(self.post_delay)
        return response.json().get('ts')

    def _create_thread_payload(self, channel_id, body, header, status_icons, status):
        return mattermost_get_create_thread_payload(channel_id, body, header, status_icons, status)

    def _post_thread_payload(self, channel_id, id_, text):
        return {'channel_id': channel_id, 'root_id': id_, 'message': text}

    def update_thread_payload(self, channel_id, id_, body, header, status_icons, status, chain_enabled,
                              status_enabled):
        return mattermost_get_update_payload(channel_id, id_, body, header, status_icons, status, chain_enabled,
                                             status_enabled)

    def _update_thread(self, id_, payload):
        self.http.put(
            f'{self.url}/api/v4/posts/{id_}',
            headers=mattermost_headers,
            data=json.dumps(payload)
        )
        sleep(self.post_delay)

    def _markdown_links_to_native_format(self, text):
        return text
