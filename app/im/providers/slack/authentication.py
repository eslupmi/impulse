"""Slack OpenID wire protocol; the core owns HTTP sessions and login policy."""
from urllib.parse import urlencode

from app.im.plugin_api import AuthenticationError, AuthenticationUser


class SlackAuthentication:
    name = 'slack'

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorize_url = 'https://slack.com/openid/connect/authorize'
        self.token_url = 'https://slack.com/api/openid.connect.token'
        self.user_url = 'https://slack.com/api/openid.connect.userInfo'

    def build_authorization_url(self, state, redirect_uri):
        return self.authorize_url + '?' + urlencode({
            'response_type': 'code', 'client_id': self.client_id,
            'redirect_uri': redirect_uri, 'state': state, 'scope': 'openid profile email',
        })

    @staticmethod
    async def _read(response):
        try:
            data = await response.json()
            if response.status != 200 or not isinstance(data, dict) or data.get('ok') is False:
                raise AuthenticationError('auth_failed', 'Slack authentication request failed')
            return data
        finally:
            response.close()

    async def authenticate_callback(self, params, redirect_uri, http):
        if params.get('error'):
            raise AuthenticationError('provider_error')
        code = params.get('code')
        if not code:
            raise AuthenticationError('missing_code')
        data = await self._read(await http.post(self.token_url, data={
            'grant_type': 'authorization_code', 'client_id': self.client_id,
            'client_secret': self.client_secret, 'code': code, 'redirect_uri': redirect_uri,
        }))
        token = data.get('access_token')
        if not token:
            raise AuthenticationError('auth_failed', 'Slack access token not found in response')
        data = await self._read(await http.get(self.user_url, headers={'Authorization': f'Bearer {token}'}))
        return self.parse_user(data)

    @staticmethod
    def parse_user(data):
        user = data.get('user')
        user_data = user if isinstance(user, dict) else data
        user_id = str(user_data.get('id') or user_data.get('user_id') or data.get('sub') or '')
        if not user_id:
            raise AuthenticationError('auth_failed', 'Slack user id not found in response')
        return AuthenticationUser(
            id=user_id,
            username=user_data.get('name') or user_data.get('username') or data.get('preferred_username'),
            full_name=user_data.get('real_name') or user_data.get('name') or data.get('name'),
            email=user_data.get('email') or data.get('email'),
        )
