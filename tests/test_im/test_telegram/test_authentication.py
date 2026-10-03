"""Telegram registered OpenID adapter and signed ID token verification."""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlsplit

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config.environment import EnvironmentConfig
from app.config.validation import ImpulseConfig
from impulse_telegram.authentication import TelegramAuthentication
from app.ui.authentication.factory import build_auth_manager
from app.ui.authentication.models.auth_session import AuthSession
from app.ui.authentication.providers.registered_provider import RegisteredAuthenticationProvider
from tests.test_im.test_provider_seam import Response


class AuthTransport:
    def __init__(self, token, jwks):
        self.token = Response({'id_token': token})
        self.jwks = Response(jwks)
        self.post = AsyncMock(return_value=self.token)
        self.get = AsyncMock(return_value=self.jwks)
        self.close = AsyncMock()
        self.initialize_client = lambda: None


def test_id_only_telegram_login_profile_keeps_alias_and_cached_name(tmp_path, monkeypatch):
    config = ImpulseConfig(messenger={
        'type': 'telegram', 'impulse_address': 'https://impulse.test',
        'channels': {'default': {'id': -100123}},
        'users': {'local-alias': {'id': 123}}, 'admin_users': [],
    }, route={'channel': 'default'})
    store = Mock()
    store.get.return_value = {'full_name': 'Platform Name', 'username': 'platform_handle'}
    monkeypatch.setattr('app.ui.authentication.factory.get_user_store', lambda: store)
    manager = build_auth_manager(config, EnvironmentConfig(data_path=str(tmp_path)))
    now = datetime.now(timezone.utc)
    session_id = 'a' * 64
    manager.session_store.save_session(AuthSession(
        session_id=session_id, user_id='123', created_at=now, expires_at=now + timedelta(hours=1),
    ))
    profile = manager.get_current_user(session_id)
    assert profile['authenticated']
    assert profile['user']['id'] == '123'
    assert profile['user']['username'] == 'local-alias'
    assert profile['user']['full_name'] == 'Platform Name'
    store.get.assert_called_once_with('123')


@pytest.mark.asyncio
async def test_registered_telegram_login_verifies_id_token(tmp_path, monkeypatch):
    config = ImpulseConfig(messenger={
        'type': 'telegram', 'impulse_address': 'https://impulse.test',
        'channels': {'default': {'id': -100123}}, 'users': {'alice': {'id': 123}}, 'admin_users': [],
    }, route={'channel': 'default'})
    environment = EnvironmentConfig(data_path=str(tmp_path), auth_client_id='client', auth_client_secret='secret')
    manager = build_auth_manager(config, environment)
    assert isinstance(manager.provider, RegisteredAuthenticationProvider)
    assert isinstance(manager.provider.provider, TelegramAuthentication)
    authorization = manager.provider.build_authorization_url('state', 'https://impulse.test/auth/callback')
    assert urlsplit(authorization).netloc == 'oauth.telegram.org'
    assert parse_qs(urlsplit(authorization).query)['scope'] == ['openid profile']

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    token = jwt.encode({
        'iss': TelegramAuthentication.ISSUER, 'aud': 'client', 'sub': '123',
        'preferred_username': 'alice', 'name': 'Alice',
        'iat': now, 'exp': now + timedelta(minutes=5),
    }, private_key, algorithm='RS256', headers={'kid': 'key-1'})
    jwks = {'keys': [json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key())) | {'kid': 'key-1'}]}
    transport = AuthTransport(token, jwks)
    monkeypatch.setattr('app.ui.authentication.providers.registered_provider.RateLimitedClient',
                        lambda **kwargs: transport)

    user = await manager.provider.authenticate_callback({'code': 'one-use'}, 'https://impulse.test/auth/callback')
    assert user.id == '123' and user.username == 'alice' and user.messenger == 'telegram'
    assert transport.post.call_args.kwargs['headers']['Authorization'].startswith('Basic ')
    assert transport.token.closed and transport.jwks.closed
    transport.close.assert_awaited_once()
