"""Slack login tests: mocked HTTP routes plus real core HTTP against a local fake API."""

from urllib.parse import parse_qs, urlsplit
from unittest.mock import AsyncMock, Mock

import pytest
from aiohttp import web
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config.environment import EnvironmentConfig
from app.config.validation import ImpulseConfig
from impulse_messenger_api import AuthenticationError
from impulse_slack.authentication import SlackAuthentication
from app.ui.authentication.factory import build_auth_manager
from app.ui.authentication.router import create_auth_router
from tests.test_im.test_provider_seam import Response


def auth_manager(tmp_path, **env):
    config = ImpulseConfig(
        messenger={
            'type': 'slack',
            'channels': {'default': {'id': 'C1'}},
            'users': {'alice': {'id': 'U1'}},
            'admin_users': [],
        },
        route={'channel': 'default'},
    )
    environment = EnvironmentConfig(
        data_path=str(tmp_path),
        auth_client_id='client',
        auth_client_secret='secret',
        auth_redirect_url='http://testserver/impulse/auth/callback',
        auth_whitelist_enabled=True,
        auth_cookie_secure=False,
        **env,
    )
    return build_auth_manager(config, environment, http_prefix='/impulse')


class AuthTransport:
    def __init__(self, token=None, user=None, status=200):
        self.token = Response({'ok': True, 'access_token': 'user-token'} if token is None else token, status)
        self.user = Response(
            {'ok': True, 'sub': 'U1', 'name': 'Alice', 'email': 'alice@example.test'} if user is None else user
        )
        self.post = AsyncMock(return_value=self.token)
        self.get = AsyncMock(return_value=self.user)
        self.initialize_client = Mock()
        self.close = AsyncMock()


def start(client):
    response = client.get('/impulse/auth/login?next=/impulse/incidents', follow_redirects=False)
    assert response.status_code == 302
    url = urlsplit(response.headers['location'])
    assert url.netloc == 'slack.com'
    params = parse_qs(url.query)
    assert params['scope'] == ['openid profile email']
    assert params['redirect_uri'] == ['http://testserver/impulse/auth/callback']
    return params['state'][0]


def client_for(manager):
    app = FastAPI()
    app.include_router(create_auth_router(manager), prefix='/impulse')
    return TestClient(app)


def test_login_callback_cookie_session_replay_and_logout(tmp_path, monkeypatch, caplog):
    manager = auth_manager(tmp_path)
    transport = AuthTransport()
    factory = Mock(return_value=transport)
    monkeypatch.setattr('app.ui.authentication.providers.registered_provider.RateLimitedClient', factory)
    with client_for(manager) as client:
        state = start(client)
        response = client.get(
            '/impulse/auth/callback', params={'state': state, 'code': 'one-shot'}, follow_redirects=False
        )
        assert response.status_code == 302 and response.headers['location'] == '/impulse/incidents'
        cookie = response.headers['set-cookie']
        assert 'HttpOnly' in cookie and 'Path=/impulse' in cookie and 'SameSite=lax' in cookie
        assert client.get('/impulse/auth/me').json()['user']['id'] == 'U1'
        assert client.get('/impulse/auth/me').json()['authenticated'] is True
        # A new manager reuses the persisted session file.
        session_id = client.cookies.get('impulse_auth_session')
        assert auth_manager(tmp_path).get_current_user(session_id)['authenticated'] is True
        replay = client.get(
            '/impulse/auth/callback', params={'state': state, 'code': 'one-shot'}, follow_redirects=False
        )
        assert replay.headers['location'] == '/impulse'
        assert any(getattr(record, 'error', None) == 'invalid_state' for record in caplog.records)
        assert client.post('/impulse/auth/logout').status_code == 204
        assert client.get('/impulse/auth/me').json() == {'authenticated': False}
    assert factory.call_args.kwargs['retry_attempts'] == 1
    transport.post.assert_awaited_once()
    assert transport.post.call_args.kwargs['data']['client_secret'] == 'secret'
    assert transport.get.call_args.kwargs['headers'] == {'Authorization': 'Bearer user-token'}
    assert transport.token.closed and transport.user.closed
    transport.close.assert_awaited_once()


@pytest.mark.parametrize(
    'token,user,status,error',
    [
        ({'ok': False, 'error': 'secret reflected by server'}, None, 200, 'auth_failed'),
        ({'ok': True}, None, 200, 'auth_failed'),
        ({'ok': True, 'access_token': 'token'}, None, 503, 'auth_failed'),
        (None, {'ok': False, 'error': 'private'}, 200, 'auth_failed'),
        (None, {'ok': True}, 200, 'auth_failed'),
        (None, {'ok': True, 'sub': 'U-not-allowed'}, 200, 'not_allowed'),
    ],
)
def test_authentication_failure_never_creates_session(tmp_path, monkeypatch, token, user, status, error, caplog):
    manager = auth_manager(tmp_path)
    transport = AuthTransport(token, user, status)
    monkeypatch.setattr(
        'app.ui.authentication.providers.registered_provider.RateLimitedClient', lambda **kwargs: transport
    )
    with client_for(manager) as client:
        state = start(client)
        response = client.get('/impulse/auth/callback', params={'state': state, 'code': 'code'}, follow_redirects=False)
        assert response.headers['location'] == '/impulse/incidents'
        assert any(getattr(record, 'error', None) == error for record in caplog.records)
        assert 'set-cookie' not in response.headers
        assert client.get('/impulse/auth/me').json() == {'authenticated': False}
    assert transport.token.closed
    if transport.get.await_count:
        assert transport.user.closed
    transport.close.assert_awaited_once()


def test_invalid_state_makes_no_provider_calls(tmp_path, monkeypatch, caplog):
    manager = auth_manager(tmp_path)
    factory = Mock()
    monkeypatch.setattr('app.ui.authentication.providers.registered_provider.RateLimitedClient', factory)
    with client_for(manager) as client:
        response = client.get('/impulse/auth/callback?state=wrong&code=code', follow_redirects=False)
        assert response.headers['location'] == '/impulse'
        assert any(getattr(record, 'error', None) == 'invalid_state' for record in caplog.records)
    factory.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('params,error', [({}, 'missing_code'), ({'error': 'access_denied'}, 'provider_error')])
async def test_provider_callback_error_without_http(params, error):
    http = AuthTransport()
    with pytest.raises(AuthenticationError) as exc:
        await SlackAuthentication('client', 'secret').authenticate_callback(params, 'http://callback', http)
    assert exc.value.code == error
    http.post.assert_not_called()


@pytest.mark.asyncio
async def test_real_core_transport_login_against_local_fake_slack(tmp_path, aiohttp_server):
    calls = []

    async def token(request):
        calls.append(('token', dict(await request.post())))
        return web.json_response({'ok': True, 'access_token': 'local-token'})

    async def user(request):
        calls.append(('user', request.headers.get('Authorization')))
        return web.json_response({'ok': True, 'sub': 'U1', 'name': 'Alice'})

    app = web.Application()
    app.router.add_post('/api/openid.connect.token', token)
    app.router.add_get('/api/openid.connect.userInfo', user)
    server = await aiohttp_server(app)
    manager = auth_manager(tmp_path)
    provider = manager.provider.provider
    provider.token_url = str(server.make_url('/api/openid.connect.token'))
    provider.user_url = str(server.make_url('/api/openid.connect.userInfo'))
    authorization = manager.start_auth('/impulse')
    state = parse_qs(urlsplit(authorization.headers['location']).query)['state'][0]
    response = await manager.handle_callback({'state': state, 'code': 'test-code'})
    assert response.headers['location'] == '/impulse'
    assert 'impulse_auth_session' in response.headers['set-cookie']
    assert calls[0][1]['redirect_uri'] == 'http://testserver/impulse/auth/callback'
    assert calls[0][1]['code'] == 'test-code'
    assert calls[1] == ('user', 'Bearer local-token')
