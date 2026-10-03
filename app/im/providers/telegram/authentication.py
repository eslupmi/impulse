"""Telegram OpenID wire protocol. Core owns HTTP transport and sessions."""
from base64 import b64encode
from urllib.parse import urlencode

import jwt

from app.im.plugin_api import AuthenticationError, AuthenticationUser


class TelegramAuthentication:
    name = 'telegram'
    ISSUER = 'https://oauth.telegram.org'

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorize_url = 'https://oauth.telegram.org/auth'
        self.token_url = 'https://oauth.telegram.org/token'
        self.jwks_url = 'https://oauth.telegram.org/.well-known/jwks.json'
        self._jwks_cache = None

    def build_authorization_url(self, state, redirect_uri):
        return self.authorize_url + '?' + urlencode({
            'response_type': 'code', 'client_id': self.client_id, 'redirect_uri': redirect_uri,
            'state': state, 'scope': 'openid profile',
        })

    @staticmethod
    async def _read(response):
        try:
            data = await response.json()
            if response.status != 200 or not isinstance(data, dict):
                raise AuthenticationError('auth_failed')
            return data
        finally:
            response.close()

    async def _fetch_jwks(self, http):
        if self._jwks_cache is None:
            self._jwks_cache = await self._read(await http.get(self.jwks_url))
        return self._jwks_cache

    async def _find_key(self, kid, http):
        jwks = await self._fetch_jwks(http)
        for key in jwks.get('keys', []):
            if kid is None or key.get('kid') == kid:
                try:
                    return jwt.PyJWK(key).key
                except jwt.PyJWTError as error:
                    raise AuthenticationError('auth_failed', 'Invalid Telegram signing key') from error
        return None

    async def authenticate_callback(self, params, redirect_uri, http):
        if params.get('error'):
            raise AuthenticationError('provider_error')
        code = params.get('code')
        if not code:
            raise AuthenticationError('missing_code')
        credentials = b64encode(f'{self.client_id}:{self.client_secret}'.encode()).decode()
        data = await self._read(await http.post(self.token_url, data={
            'grant_type': 'authorization_code', 'code': code, 'redirect_uri': redirect_uri,
            'client_id': self.client_id,
        }, headers={'Authorization': f'Basic {credentials}'}))
        token = data.get('id_token')
        if not token:
            raise AuthenticationError('auth_failed', 'Telegram id_token not found in response')
        try:
            kid = jwt.get_unverified_header(token).get('kid')
        except jwt.PyJWTError as error:
            raise AuthenticationError('auth_failed', 'Invalid id_token format') from error
        key = await self._find_key(kid, http)
        if key is None:
            self._jwks_cache = None
            key = await self._find_key(kid, http)
        if key is None:
            raise AuthenticationError('auth_failed', 'No matching key in Telegram JWKS')
        try:
            claims = jwt.decode(token, key, algorithms=['RS256', 'ES256'],
                                audience=self.client_id, issuer=self.ISSUER)
        except jwt.PyJWTError as error:
            raise AuthenticationError('auth_failed', 'id_token validation failed') from error
        user_id = str(claims.get('id') or claims.get('sub') or '')
        if not user_id:
            raise AuthenticationError('auth_failed', 'Telegram user id not found in id_token')
        return AuthenticationUser(id=user_id, username=claims.get('preferred_username'), full_name=claims.get('name'))
