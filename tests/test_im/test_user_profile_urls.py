import pytest

from app.config.validation import MessengerType
from app.im.application import Application
from app.im.providers.mattermost import MattermostProvider
from app.im.providers.slack import SlackProvider
from app.im.plugin_api import ProviderIdentity, UserProfile
from app.im.users import ProfileUser as SlackUser
from app.im.providers.telegram import TelegramProvider


@pytest.mark.asyncio
async def test_init_public_url_strips_trailing_slash():
    app = Application.__new__(Application)
    app.type = MessengerType.SLACK
    app.url = "https://slack.com"
    app._app_config = None

    async def public_url(_config):
        return "https://example.slack.com/"

    app._get_public_url = public_url
    assert await app._init_public_url() == "https://example.slack.com"


def test_slack_user_profile_url():
    app = Application.__new__(Application)
    app.public_url = "https://example.slack.com"
    user = SlackUser("alice", "U123", exists=True, full_name="Alice", username="alice")

    assert SlackProvider.user_url(UserProfile(user.id, user.exists), ProviderIdentity(app.public_url)) == "https://example.slack.com/team/U123"


def test_mattermost_user_profile_url():
    assert MattermostProvider.user_url(
        UserProfile("U123", True, username="alice"), ProviderIdentity("https://mm.example.com", "team1"),
    ) == "https://mm.example.com/team1/users/U123"


def test_telegram_user_profile_url_with_username():
    assert TelegramProvider.user_url(UserProfile(12345, True, username='alice'), ProviderIdentity()) == 'https://t.me/alice'


def test_telegram_user_profile_url_without_username():
    assert TelegramProvider.user_url(UserProfile(12345, True), ProviderIdentity()) is None
