from app.config.environment import get_environment_config
from app.config.validation import ApplicationConfig, MattermostApplicationConfig
import asyncio

import aiohttp
from app.im.mattermost.threads import (
    mattermost_get_create_thread_payload,
    mattermost_get_update_payload,
)
from app.im.users import BaseUser
from app.logging import logger


from app.im.providers.legacy import LegacyProviderAdapter
from app.im.plugin_api import ProviderDescriptor


class MattermostProvider(LegacyProviderAdapter):
    descriptor = ProviderDescriptor("mattermost", rate_limit=10, rate_window_seconds=1.0)

    async def get_all_groups(self):
        """Unused function for Mattermost"""
        return {}

    async def get_group_details(self, group_id: str):
        """Fetch a single group from Mattermost API using /api/v4/groups/<group_id>"""
        if not group_id:
            return {'id': None, 'name': None, 'exists': False}

        try:
            response = await self.http.get(  # type: ignore[union-attr]
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
        except (asyncio.TimeoutError, aiohttp.ClientConnectionError) as e:
            logger.error("Group details fetch error", extra={'group_id': group_id, 'error': str(e)})
            return {'id': group_id, 'name': None, 'exists': False}

    async def get_user_details(self, user_details):
        id_ = user_details.get('id')
        response = await self.http.get(f'{self.url}/api/v4/users/{id_}?user_id={id_}', headers=self.headers)

        if response.status == 404:
            logger.debug("User not found", extra={'user_id': id_})
            response.close()
            return {'id': id_, 'username': None, 'exists': False, 'full_name': None,
                    'email': None, 'timezone': None}

        if response.status != 200:
            logger.debug("User details fetch failed", extra={'user_id': id_, 'status': response.status})
            response.close()
            return {'id': id_, 'username': None, 'exists': False, 'full_name': None,
                    'email': None, 'timezone': None}

        data = await self._read_response_json(response)
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        full_name = f"{first_name} {last_name}".strip()
        return {
            'id': id_,
            'username': data.get('username'),
            'exists': True,
            'full_name': full_name,
            'email': data.get('email'),
            'timezone': self._extract_timezone(data.get('timezone'))
        }

    def update_incident_payload(self, incident, body, header, status_icons, tz_str=None, **kwargs):
        return mattermost_get_update_payload(incident, body, header, status_icons, tz_str)

    @staticmethod
    def _extract_timezone(timezone_data):
        if not timezone_data or not isinstance(timezone_data, dict):
            return None
        use_automatic = timezone_data.get('useAutomaticTimezone')
        if use_automatic == 'true':
            return timezone_data.get('automaticTimezone') or None
        return timezone_data.get('manualTimezone') or None

    def _get_incident_message_payload(self, incident, body, header, status_icons):
        return mattermost_get_create_thread_payload(incident, body, header, status_icons)

    async def _get_public_url(self, app_config: ApplicationConfig):
        assert isinstance(app_config, MattermostApplicationConfig)
        return app_config.address

    def _get_team_name(self, app_config: ApplicationConfig):
        assert isinstance(app_config, MattermostApplicationConfig)
        return app_config.team

    def _get_url(self, app_config: ApplicationConfig):
        assert isinstance(app_config, MattermostApplicationConfig)
        return app_config.address

    def _build_user_profile_url(self, user_id: str, user: BaseUser) -> str | None:
        return f"{self.public_url}/{self.team}/users/{user_id}"

    def _initialize_specific_params(self):
        self.post_message_url = f'{self.url}/api/v4/posts'
        env_config = get_environment_config()
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {env_config.mattermost_access_token}',
        }
        self.rate_limit = 10
        self.thread_id_key = 'id'

    def _markdown_links_to_native_format(self, text):
        return text

    def _post_thread_payload(self, channel_id, id_, text):
        return {'channel_id': channel_id, 'root_id': id_, 'message': text}

    async def _update_incident_message(self, id_, payload):
        response = await self.http.put(
            f'{self.url}/api/v4/posts/{id_}',
            headers=self.headers,
            json=payload
        )
        response.close()

    def user_url(self, user, identity):
        return f"{identity.public_url}/{identity.team}/users/{user.id}"
