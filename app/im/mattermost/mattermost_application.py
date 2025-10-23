import asyncio

import aiohttp
from fastapi.responses import JSONResponse

from app.im.application import Application
from app.im.colors import status_colors
from app.im.mattermost.config import (mattermost_request_delay, mattermost_bold_text,
                                      mattermost_env, mattermost_admins_template_string)
from app.im.mattermost.threads import mattermost_get_create_thread_payload, mattermost_get_update_payload, \
    mattermost_get_button_update_payload
from app.im.mattermost.user import User
from app.logging import logger
from app.config.config import get_config
from app.config.validation import ApplicationConfig, MattermostUser


class MattermostApplication(Application):

    def __init__(self, app_config: ApplicationConfig, channels, default_channel):
        super().__init__(app_config, channels, default_channel)

    def _initialize_specific_params(self):
        self.post_message_url = f'{self.url}/api/v4/posts'
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {get_config().mattermost_access_token}',
        }
        self.post_delay = mattermost_request_delay
        self.thread_id_key = 'id'

    async def _get_channels(self, team):
        try:
            async with self.http.get(
                f"{self.url}/api/v4/teams/{team['id']}/channels",
                params={'per_page': 1000},
                headers=self.headers
            ) as response:
                response.raise_for_status()
                await asyncio.sleep(self.post_delay)
                data = await response.json()
                return {c.get('name'): c for c in data}
        except aiohttp.ClientError as e:
            logger.error(f'Failed to retrieve channel list: {e}')
            return {}

    def _get_url(self, app_config: ApplicationConfig):
        return app_config.address

    def _get_public_url(self, app_config: ApplicationConfig):
        return app_config.address

    def _get_team_name(self, app_config: ApplicationConfig):
        logger.info(f'Get {self.type.value.capitalize()} team name')
        return app_config.team

    async def get_user_details(self, user_details):
        id_ = user_details.get('id')
        async with self.http.get(f'{self.url}/api/v4/users/{id_}?user_id={id_}', headers=self.headers) as response:
            if response.status == 404:
                logger.debug(f'Failed to get user details for ID {id_}: Not Found (HTTP 404)')
                return {'id': id_, 'username': None, 'exists': False, 'full_name': None}

            if response.status != 200:
                logger.debug(f'Failed to get user details for {id_}: HTTP {response.status}')
                return {'id': id_, 'username': None, 'exists': False, 'full_name': None}

            data = await response.json()
            first_name = data.get('first_name', '').strip()
            last_name = data.get('last_name', '').strip()
            full_name = f"{first_name} {last_name}".strip()
            return {'id': id_, 'username': data.get('username'), 'exists': True, 'full_name': full_name}

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

    async def send_message(self, channel_id, text, attachment):
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
        async with self.http.post(f'{self.url}/api/v4/posts', headers=self.headers, json=payload) as response:
            await asyncio.sleep(self.post_delay)
            response_json = await response.json()
            return response_json.get('ts')

    async def buttons_handler(self, payload, incidents, queue_, route):
        post_id = payload['post_id']
        incident_ = incidents.get_by_ts(ts=post_id)
        if incident_ is None:
            return JSONResponse(payload, status_code=200)
        action = payload['context']['action']

        user_id = payload.get('user_id')
        user_name = payload.get('user_name')

        if action == 'chain':
            await queue_.delete_by_id(incident_.uuid, delete_steps=True, delete_status=False)
            if incident_.chain_enabled or incident_.status != 'resolved':
                # if user is already assigned, do nothing
                if incident_.assigned_user_id == user_id:
                    logger.info(f'Incident {incident_.uuid} -> button TAKE IT pressed, but user is already assigned')
                    return JSONResponse(payload, status_code=200)
                else:
                    logger.info(f'Incident {incident_.uuid} -> button TAKE IT pressed, assigning to {user_id}')
                    incident_.assign_user_id(user_id)
                    incident_.assign_user(user_name)
                    asyncio.create_task(self.post_assignment_notification(incident_, user_id, user_name))
                    asyncio.create_task(self.fetch_and_assign_user_name(incident_, user_id, incidents))
                    await asyncio.gather(task_assignment, task_fetch)
                incident_.chain_enabled = False
            else: # release
                logger.info(f'Incident {incident_.uuid} -> button RELEASE pressed')
                asyncio.create_task(self.post_unassignment_notification(incident_))
                await task_unassignment
                incident_.release()
        elif action == 'status':
            if incident_.status_enabled:
                logger.info(f'Incident {incident_.uuid} -> button STATUS pressed (disabled)')
                incident_.status_enabled = False
            else:
                logger.info(f'Incident {incident_.uuid} -> button STATUS pressed (enabled)')
                incident_.status_enabled = True
        incident_.dump()
        status_icons = self.status_icons_template.form_message(incident_.payload, incident_)
        header = self.header_template.form_message(incident_.payload, incident_)
        message = self.body_template.form_message(incident_.payload, incident_)
        payload = mattermost_get_button_update_payload(
            message,
            header,
            status_icons,
            incident_.status,
            incident_.chain_enabled,
            incident_.status_enabled)
        return JSONResponse(payload, status_code=200)

    def _create_thread_payload(self, channel_id, body, header, status_icons, status):
        return mattermost_get_create_thread_payload(channel_id, body, header, status_icons, status)

    def _post_thread_payload(self, channel_id, id_, text):
        return {'channel_id': channel_id, 'root_id': id_, 'message': text}

    def update_thread_payload(self, channel_id, id_, body, header, status_icons, status, chain_enabled,
                              status_enabled):
        return mattermost_get_update_payload(channel_id, id_, body, header, status_icons, status, chain_enabled,
                                             status_enabled)

    async def _update_thread(self, id_, payload):
        async with self.http.put(
            f'{self.url}/api/v4/posts/{id_}',
            headers=self.headers,
            json=payload
        ):
            await asyncio.sleep(self.post_delay)

    def _markdown_links_to_native_format(self, text):
        return text
