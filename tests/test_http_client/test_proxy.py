from unittest.mock import MagicMock, patch

from app.http_client.proxy import http_proxy_url, requests_proxies


class TestHttpProxyHelpers:
    def test_http_proxy_url_returns_proxy(self):
        mock_env = MagicMock()
        mock_env.proxy_url = 'http://proxy.example.com:8080'
        with patch('app.http_client.proxy.get_environment_config', return_value=mock_env):
            assert http_proxy_url() == 'http://proxy.example.com:8080'

    def test_http_proxy_url_returns_none_when_unset(self):
        mock_env = MagicMock()
        mock_env.proxy_url = None
        with patch('app.http_client.proxy.get_environment_config', return_value=mock_env):
            assert http_proxy_url() is None

    def test_requests_proxies_maps_http_and_https(self):
        mock_env = MagicMock()
        mock_env.proxy_url = 'http://proxy.example.com:8080'
        with patch('app.http_client.proxy.get_environment_config', return_value=mock_env):
            assert requests_proxies() == {
                'http': 'http://proxy.example.com:8080',
                'https': 'http://proxy.example.com:8080',
            }

    def test_requests_proxies_none_when_unset(self):
        mock_env = MagicMock()
        mock_env.proxy_url = None
        with patch('app.http_client.proxy.get_environment_config', return_value=mock_env):
            assert requests_proxies() is None
