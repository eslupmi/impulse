import re


from app.config.environment import get_environment_config
from app.config.validation import ApplicationConfig
from app.im.slack.threads import get_incident_message_payload, slack_get_update_payload
from app.im.users import BaseUser
from app.logging import logger


from app.im.providers.legacy import LegacyProviderAdapter
from app.im.plugin_api import ProviderDescriptor


class SlackProvider(LegacyProviderAdapter):
    descriptor = ProviderDescriptor("slack", rate_limit=10, rate_window_seconds=1.0)

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

    async def get_user_details(self, user_details):
        id_ = user_details.get('id')
        response = await self.http.get(f'{self.url}/api/users.info?user={id_}', headers=self.headers)
        if response.status != 200:
            logger.debug("User details fetch failed", extra={'user_id': id_, 'status': response.status})
            response.close()
            return {'id': id_, 'exists': False, 'full_name': None, 'username': None,
                    'first_name': None, 'last_name': None, 'email': None, 'timezone': None}

        data = await self._read_response_json(response)
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

    def update_incident_payload(self, incident, body, header, status_icons, tz_str=None, **kwargs):
        return slack_get_update_payload(incident, body, header, status_icons, tz_str)

    def _get_incident_message_payload(self, incident, body, header, status_icons):
        return get_incident_message_payload(incident, body, header, status_icons, None)

    async def _get_public_url(self, app_config: ApplicationConfig):
        response = await self.http.get(  # type: ignore[union-attr]
            f'{self.url}/api/auth.test',
            headers=self.headers
        )
        json_ = await self._read_response_json(response)
        return json_.get('url')

    def _get_team_name(self, app_config: ApplicationConfig):
        return None

    def _get_url(self, app_config: ApplicationConfig):
        return get_environment_config().dev_messenger_custom_address or 'https://slack.com'

    def _build_user_profile_url(self, user_id: str, user: BaseUser) -> str | None:
        return f"{self.public_url}/team/{user_id}"

    def _initialize_specific_params(self):
        self.post_message_url = f'{self.url}/api/chat.postMessage'
        env_config = get_environment_config()
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {env_config.slack_bot_user_oauth_token}',
        }
        self.rate_limit = 10
        self.thread_id_key = 'ts'

    def _post_thread_payload(self, channel_id, id_, text):
        return {'channel': channel_id, 'thread_ts': id_, 'text': text, 'unfurl_links': False, 'unfurl_media': False}

    def _markdown_links_to_native_format(self, text):
        def replace_link(match):
            link_text = match.group(1)
            url = match.group(2)
            return f'<{url}|{link_text}>'

        pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        converted_text = re.sub(pattern, replace_link, text, flags=re.DOTALL)
        return converted_text

    async def _update_incident_message(self, id_, payload):
        response = await self.http.post(
            f'{self.url}/api/chat.update',
            headers=self.headers,
            json=payload
        )
        response.close()

    def user_url(self, user, identity):
        return f"{identity.public_url}/team/{user.id}"
