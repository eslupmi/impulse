from unittest.mock import patch

from app.http_client.session import create_client_session


class TestCreateClientSession:
    def test_sets_trust_env_true_by_default(self):
        with patch('app.http_client.session.ClientSession') as mock_session_class:
            create_client_session(timeout='timeout')

        mock_session_class.assert_called_once_with(timeout='timeout', trust_env=True)

    def test_allows_explicit_trust_env_override(self):
        with patch('app.http_client.session.ClientSession') as mock_session_class:
            create_client_session(trust_env=False)

        mock_session_class.assert_called_once_with(trust_env=False)
