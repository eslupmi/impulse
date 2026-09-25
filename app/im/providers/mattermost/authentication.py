"""Mattermost OAuth wire protocol; the core owns HTTP sessions and login policy."""
from urllib.parse import urlencode

from app.im.plugin_api import AuthenticationError, AuthenticationUser


class MattermostAuthentication:
    name = 'mattermost'

    def __init__(self, base_url, client_id, client_secret):
        base_url = base_url.rstrip('/')
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorize_url = f'{base_url}/oauth/authorize'
        self.token_url = f'{base_url}/oauth/access_token'
        self.user_url = f'{base_url}/api/v4/users/me'

    def build_authorization_url(self, state, redirect_uri):
        return self.authorize_url + '?' + urlencode({
            'response_type': 'code', 'client_id': self.client_id, 'redirect_uri': redirect_uri,
            'state': state, 'scope': 'openid profile email',
        })

    @staticmethod
    async def _read(response):
        try:
            data = await response.json()
            if response.status != 200 or not isinstance(data, dict):
                raise AuthenticationError('auth_failed', 'Mattermost authentication request failed')
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
            raise AuthenticationError('auth_failed', 'Mattermost access token not found in response')
        data = await self._read(await http.get(self.user_url, headers={'Authorization': f'Bearer {token}'}))
        return self.parse_user(data)

    @staticmethod
    def parse_user(data):
        user_id = str(data.get('id') or '')
        if not user_id:
            raise AuthenticationError('auth_failed', 'Mattermost user id not found in response')
        full_name = f"{(data.get('first_name') or '').strip()} {(data.get('last_name') or '').strip()}".strip() or None
        return AuthenticationUser(id=user_id, username=data.get('username'), full_name=full_name, email=data.get('email'))
