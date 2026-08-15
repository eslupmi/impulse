import pytest

from app.config.validation import MessengerType
from app.im.mattermost.user import User as MattermostUser
from app.im.mattermost.mattermost_application import MattermostApplication
from app.im.slack.slack_application import SlackApplication
from app.im.slack.user import User as SlackUser
from app.im.telegram.telegram_application import TelegramApplication
from app.im.telegram.user import User as TelegramUser


@pytest.mark.asyncio
async def test_init_public_url_strips_trailing_slash():
    app = SlackApplication.__new__(SlackApplication)
    app.type = MessengerType.SLACK
    app.url = "https://slack.com"
    app._app_config = None

    async def public_url(_config):
        return "https://example.slack.com/"

    app._get_public_url = public_url
    assert await app._init_public_url() == "https://example.slack.com"


def test_slack_user_profile_url():
    app = SlackApplication.__new__(SlackApplication)
    app.public_url = "https://example.slack.com"
    user = SlackUser("alice", "U123", exists=True, full_name="Alice", username="alice")

    assert app._build_user_profile_url("U123", user) == "https://example.slack.com/team/U123"


def test_mattermost_user_profile_url():
    app = MattermostApplication.__new__(MattermostApplication)
    app.public_url = "https://mm.example.com"
    app.team = "team1"
    user = MattermostUser("alice", "U123", username="alice", exists=True, full_name="Alice")

    assert app._build_user_profile_url("U123", user) == "https://mm.example.com/team1/users/U123"


def test_telegram_user_profile_url_with_username():
    app = TelegramApplication.__new__(TelegramApplication)
    user = TelegramUser("alice", 12345, exists=True, full_name="Alice", username="alice")

    assert app._build_user_profile_url("12345", user) == "https://t.me/alice"


def test_telegram_user_profile_url_without_username():
    app = TelegramApplication.__new__(TelegramApplication)
    user = TelegramUser("alice", 12345, exists=True, full_name="Alice")

    assert app._build_user_profile_url("12345", user) is None
