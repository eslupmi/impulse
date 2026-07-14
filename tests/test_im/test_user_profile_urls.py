from app.im.mattermost.user import User as MattermostUser
from app.im.mattermost.mattermost_application import MattermostApplication
from app.im.slack.slack_application import SlackApplication
from app.im.slack.user import User as SlackUser
from app.im.telegram.telegram_application import TelegramApplication
from app.im.telegram.user import User as TelegramUser


def test_slack_user_profile_url():
    app = SlackApplication.__new__(SlackApplication)
    app.public_url = "https://example.slack.com/"
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
