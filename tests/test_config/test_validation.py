"""
Unit tests for app.config.validation module.
"""
import pytest
from pydantic import ValidationError

from app.config.validation import (
    ImpulseConfig, SlackApplicationConfig, MattermostApplicationConfig,
    TelegramApplicationConfig, RouteConfig, WebhookConfig,
    ScheduleChain, CloudChain, SimpleChainStep, UIConfig, UIColumn,
    UISorting, IncidentTimeouts, IncidentNotifications,
    UserGroup, TemplateFiles, validate_config, MessengerType
)
from tests.utils import (
    create_slack_config_data, create_mattermost_config_data,
    create_telegram_config_data, create_incident_config_data,
    create_webhook_config_data
)


class TestMessengerType:
    """Test cases for MessengerType enum."""

    def test_messenger_type_values(self):
        """Test MessengerType enum values."""
        assert MessengerType.SLACK.value == "slack"
        assert MessengerType.MATTERMOST.value == "mattermost"
        assert MessengerType.TELEGRAM.value == "telegram"
        assert MessengerType.NONE.value == "none"

    def test_messenger_type_from_string(self):
        """Test creating MessengerType from string."""
        assert MessengerType("slack") == MessengerType.SLACK
        assert MessengerType("mattermost") == MessengerType.MATTERMOST
        assert MessengerType("telegram") == MessengerType.TELEGRAM
        assert MessengerType("none") == MessengerType.NONE

    def test_messenger_type_invalid_string(self):
        """Test creating MessengerType with invalid string."""
        with pytest.raises(ValueError):
            MessengerType("invalid")


class TestSlackApplicationConfig:
    """Test cases for SlackApplicationConfig."""

    def test_slack_config_creation(self):
        """Test creating SlackApplicationConfig with valid data."""
        config = SlackApplicationConfig(
            type=MessengerType.SLACK,
            admin_users=["admin1", "admin2"],
            channels={"default": {"id": "C123456789"}},
            users={"admin1": {"id": "U123456"}},
            template_files={}
        )

        assert config.type == MessengerType.SLACK
        assert config.admin_users == ["admin1", "admin2"]
        assert "default" in config.channels
        assert config.channels["default"].id == "C123456789"
        assert "admin1" in config.users
        assert config.users["admin1"].id == "U123456"
        assert config.template_files.status_icons is None

    def test_slack_config_with_template_files(self):
        """Test SlackApplicationConfig with template files."""
        template_files = {
            "header": "slack_header.j2",
            "body": "slack_body.j2",
            "status_icons": "slack_status_icons.j2"
        }

        config = SlackApplicationConfig(
            type=MessengerType.SLACK,
            admin_users=["admin1"],
            channels={"default": {"id": "C123456789"}},
            users={"admin1": {"id": "U123456"}},
            template_files=template_files
        )

        assert config.template_files.header == "slack_header.j2"
        assert config.template_files.body == "slack_body.j2"
        assert config.template_files.status_icons == "slack_status_icons.j2"

    def test_slack_config_missing_required_fields(self):
        """Test SlackApplicationConfig with missing required fields."""
        with pytest.raises(ValidationError):
            SlackApplicationConfig(
                type=MessengerType.SLACK
                # Missing channels, users, template_files
            )


class TestMattermostApplicationConfig:
    """Test cases for MattermostApplicationConfig."""

    def test_mattermost_config_creation(self):
        """Test creating MattermostApplicationConfig with valid data."""
        config = MattermostApplicationConfig(
            type=MessengerType.MATTERMOST,
            admin_users=["admin1"],
            channels={"default": {"id": "channel123"}},
            users={"admin1": {"id": "user123"}},
            template_files={},
            address="https://mattermost.example.com",
            team="test-team",
            impulse_address="https://impulse.example.com"
        )

        assert config.type == MessengerType.MATTERMOST
        assert "default" in config.channels
        assert config.channels["default"].id == "channel123"
        assert "admin1" in config.users
        assert config.users["admin1"].id == "user123"
        assert config.template_files.status_icons is None
        assert config.address == "https://mattermost.example.com"
        assert config.team == "test-team"
        assert config.impulse_address == "https://impulse.example.com"


class TestTelegramApplicationConfig:
    """Test cases for TelegramApplicationConfig."""

    def test_telegram_config_creation(self):
        """Test creating TelegramApplicationConfig with valid data."""
        config = TelegramApplicationConfig(
            type=MessengerType.TELEGRAM,
            admin_users=["admin1"],
            channels={"default": {"id": -1001234567890}},
            users={"admin1": {"id": 123456789}},
            template_files={},
            impulse_address="https://impulse.example.com"
        )

        assert config.type == MessengerType.TELEGRAM
        assert "default" in config.channels
        assert config.channels["default"].id == -1001234567890
        assert "admin1" in config.users
        assert config.users["admin1"].id == 123456789
        assert config.template_files.status_icons is None
        assert config.impulse_address == "https://impulse.example.com"


class TestRouteConfig:
    """Test cases for RouteConfig."""

    def test_route_config_creation(self):
        """Test creating RouteConfig with valid data."""
        config = RouteConfig(
            channel="default",
            chain="test_chain",
            routes=[],
            matchers=["severity=critical"]
        )

        assert config.channel == "default"
        assert config.chain == "test_chain"
        assert config.routes == []
        assert config.matchers == ["severity=critical"]

    def test_route_config_with_nested_routes(self):
        """Test RouteConfig with nested routes."""
        nested_route = RouteConfig(
            channel="nested",
            chain="nested_chain",
            routes=[],
            matchers=["service=api"]
        )

        config = RouteConfig(
            channel="default",
            chain="main_chain",
            routes=[nested_route],
            matchers=["severity=critical"]
        )

        assert len(config.routes) == 1
        assert config.routes[0].channel == "nested"
        assert config.routes[0].chain == "nested_chain"

    def test_route_config_missing_required_fields(self):
        """Test RouteConfig with missing required fields."""
        with pytest.raises(ValidationError):
            RouteConfig(
                # Missing channel (required field)
            )


class TestWebhookConfig:
    """Test cases for WebhookConfig."""

    def test_webhook_config_creation(self):
        """Test creating WebhookConfig with valid data."""
        config = WebhookConfig(
            url="https://example.com/webhook",
            data={"message": "test"},
            auth="user:pass"
        )

        assert config.url == "https://example.com/webhook"
        assert config.data == {"message": "test"}
        assert config.auth == "user:pass"
        assert config.json_payload is None

    def test_webhook_config_with_json(self):
        """Test WebhookConfig with JSON payload."""
        config = WebhookConfig(
            url="https://example.com/webhook",
            json={"message": "test", "severity": "high"}
        )

        assert config.url == "https://example.com/webhook"
        assert config.json_payload == {"message": "test", "severity": "high"}
        assert config.data == {}

    def test_webhook_config_missing_url(self):
        """Test WebhookConfig with missing URL."""
        with pytest.raises(ValidationError):
            WebhookConfig(
                data={"message": "test"}
                # Missing url
            )


class TestSimpleChainStep:
    """Test cases for SimpleChainStep."""

    def test_chain_step_creation(self):
        """Test creating SimpleChainStep with valid data."""
        step = SimpleChainStep(user="testuser")

        assert step.user == "testuser"
        assert step.user_group is None
        assert step.webhook is None
        assert step.chain is None
        assert step.wait is None

    def test_chain_step_with_wait(self):
        """Test SimpleChainStep with wait duration."""
        step = SimpleChainStep(wait="5m")

        assert step.wait == "5m"
        assert step.user is None

    def test_chain_step_with_webhook(self):
        """Test SimpleChainStep with webhook."""
        step = SimpleChainStep(webhook="test_webhook")

        assert step.webhook == "test_webhook"
        assert step.user is None

    def test_chain_step_multiple_types_error(self):
        """Test SimpleChainStep with multiple step types (should fail)."""
        with pytest.raises(ValidationError):
            SimpleChainStep(user="testuser", webhook="test_webhook")

    def test_chain_step_no_types_error(self):
        """Test SimpleChainStep with no step types (should fail)."""
        with pytest.raises(ValidationError):
            SimpleChainStep()

    def test_chain_step_wait_format_validation(self):
        """Test SimpleChainStep wait format validation."""
        # Valid formats
        SimpleChainStep(wait="5m")
        SimpleChainStep(wait="1h")
        SimpleChainStep(wait="30s")
        SimpleChainStep(wait="2d")

        # Invalid format
        with pytest.raises(ValidationError):
            SimpleChainStep(wait="invalid")

    def test_chain_step_methods(self):
        """Test SimpleChainStep utility methods."""
        step = SimpleChainStep(user="testuser")

        assert step.get_type_and_value() == ("user", "testuser")
        assert step.get_type() == "user"
        assert step.get_value() == "testuser"
        assert not step.has_chain()

        chain_step = SimpleChainStep(chain="nested_chain")
        assert chain_step.has_chain()


class TestScheduleChain:
    """Test cases for ScheduleChain."""

    def test_schedule_chain_creation(self):
        """Test creating ScheduleChain with valid data."""
        config = ScheduleChain(
            type="schedule",
            timezone="UTC",
            schedule=[]
        )

        assert config.type == "schedule"
        assert config.timezone == "UTC"
        assert config.schedule == []

    def test_schedule_chain_with_custom_timezone(self):
        """Test ScheduleChain with custom timezone."""
        config = ScheduleChain(
            type="schedule",
            timezone="America/New_York",
            schedule=[]
        )

        assert config.timezone == "America/New_York"


class TestCloudChain:
    """Test cases for CloudChain."""

    def test_cloud_chain_creation(self):
        """Test creating CloudChain with valid data."""
        config = CloudChain(
            type="cloud",
            provider="google",
            calendar_id="test@example.com",
            default_steps=[]
        )

        assert config.type == "cloud"
        assert config.provider == "google"
        assert config.calendar_id == "test@example.com"
        assert config.default_steps == []

    def test_cloud_chain_missing_calendar_id(self):
        """Test CloudChain with missing calendar_id."""
        with pytest.raises(ValidationError):
            CloudChain(
                type="cloud",
                provider="google",
                default_steps=[]
                # Missing calendar_id
            )


class TestValidateConfig:
    """Test cases for validate_config function."""

    def test_validate_config_slack(self):
        """Test validating Slack configuration."""
        config_data = create_slack_config_data()

        config = validate_config(config_data)

        assert isinstance(config, ImpulseConfig)
        assert config.messenger.type == MessengerType.SLACK
        assert config.route.channel == "default"
        assert config.ui is not None

    def test_validate_config_mattermost(self):
        """Test validating Mattermost configuration."""
        config_data = create_mattermost_config_data()

        config = validate_config(config_data)

        assert config.messenger.type == MessengerType.MATTERMOST

    def test_validate_config_telegram(self):
        """Test validating Telegram configuration."""
        config_data = create_telegram_config_data()

        config = validate_config(config_data)

        assert config.messenger.type == MessengerType.TELEGRAM

    def test_validate_config_with_webhooks(self):
        """Test validating configuration with webhooks."""
        config_data = create_slack_config_data()
        config_data["webhooks"] = {
            "test_webhook": create_webhook_config_data()
        }

        config = validate_config(config_data)

        assert "test_webhook" in config.webhooks
        assert config.webhooks["test_webhook"].url == "https://example.com/webhook"

    def test_validate_config_with_chains(self):
        """Test validating configuration with chains."""
        config_data = create_slack_config_data(
            chains={
                "test_chain": {
                    "type": "schedule",
                    "schedule": []
                }
            }
        )

        config = validate_config(config_data)

        assert "test_chain" in config.messenger.chains
        assert config.messenger.chains["test_chain"].type == "schedule"

    def test_validate_config_invalid_messenger_type(self):
        """Test validating configuration with invalid messenger type."""
        config_data = create_slack_config_data()
        config_data["messenger"]["type"] = "invalid_type"

        with pytest.raises(ValidationError):
            validate_config(config_data)

    def test_validate_config_missing_required_fields(self):
        """Test validating configuration with missing required fields."""
        config_data = {
            "messenger": {
                "type": "slack"
                # Missing admin_users, channels, users, template_files
            }
        }

        with pytest.raises(ValidationError):
            validate_config(config_data)

    def test_validate_config_empty_data(self):
        """Test validating empty configuration data."""
        with pytest.raises(ValidationError):
            validate_config({})

    def test_validate_config_with_incident_config(self):
        """Test validating configuration with incident settings."""
        config_data = create_slack_config_data()
        config_data["incident"] = create_incident_config_data()

        config = validate_config(config_data)

        assert config.incident.notifications.assignment is True
        assert config.incident.notifications.new_firing is True
        assert config.incident.notifications.partial_resolved is False
        assert config.incident.timeouts.firing == "6h"
        assert config.incident.timeouts.unknown == "1h"
        assert config.incident.timeouts.resolved == "5m"


class TestUIConfig:
    """Test cases for UIConfig."""

    def test_ui_config_creation(self):
        """Test creating UIConfig with valid data."""
        columns = [
            {"name": "status", "header": "Status", "value": "status"},
            {"name": "created", "header": "Created", "value": "created", "type": "datetime"}
        ]

        config = UIConfig(columns=columns)

        assert len(config.columns) == 2
        assert config.columns[0].name == "status"
        assert config.columns[1].type == "datetime"

    def test_ui_config_with_sorting(self):
        """Test UIConfig with sorting rules."""
        columns = [{"name": "status", "header": "Status", "value": "status"}]
        sorting = [
            {"status": "asc"},
            {"created": "desc"}
        ]

        config = UIConfig(columns=columns, sorting=sorting)

        assert len(config.sorting) == 2
        assert config.sorting[0].column_name == "status"
        assert config.sorting[0].sort_order == "asc"

    def test_ui_config_with_colors_and_filters(self):
        """Test UIConfig with colors and filters."""
        columns = [{"name": "status", "header": "Status", "value": "status"}]
        colors = {"status": {"firing": "red", "resolved": "green"}}
        filters = ["firing", "resolved"]

        config = UIConfig(columns=columns, colors=colors, filters=filters)

        assert config.colors == colors
        assert config.filters == filters


class TestUIColumn:
    """Test cases for UIColumn."""

    def test_ui_column_creation(self):
        """Test creating UIColumn with valid data."""
        column = UIColumn(
            name="status",
            header="Status",
            value="status",
            type="string",
            visible=True
        )

        assert column.name == "status"
        assert column.header == "Status"
        assert column.value == "status"
        assert column.type == "string"
        assert column.visible is True

    def test_ui_column_link_type_validation(self):
        """Test UIColumn link type validation."""
        # Valid link column
        column = UIColumn(
            name="link",
            header="Link",
            value="link",
            type="link",
            url="https://example.com"
        )
        assert column.type == "link"
        assert column.url == "https://example.com"

        # Invalid link column (missing URL)
        with pytest.raises(ValidationError):
            UIColumn(
                name="link",
                header="Link",
                value="link",
                type="link"
                # Missing url
            )


class TestUISorting:
    """Test cases for UISorting."""

    def test_ui_sorting_creation(self):
        """Test creating UISorting with valid data."""
        sorting = UISorting(
            column_name="status",
            sort_order="asc"
        )

        assert sorting.column_name == "status"
        assert sorting.sort_order == "asc"
        assert sorting.order is None

    def test_ui_sorting_custom_order(self):
        """Test UISorting with custom order."""
        sorting = UISorting(
            column_name="status",
            sort_order="none",
            order=["firing", "resolved", "unknown"]
        )

        assert sorting.column_name == "status"
        assert sorting.sort_order == "none"
        assert sorting.order == ["firing", "resolved", "unknown"]

    def test_ui_sorting_custom_order_validation(self):
        """Test UISorting custom order validation."""
        with pytest.raises(ValidationError):
            UISorting(
                column_name="status",
                sort_order="none"
                # Missing order field
            )

    def test_ui_sorting_from_dict(self):
        """Test UISorting.from_dict method."""
        sort_dict = {"status": "asc"}
        sorting = UISorting.from_dict(sort_dict)

        assert sorting.column_name == "status"
        assert sorting.sort_order == "asc"

    def test_ui_sorting_to_dict(self):
        """Test UISorting.to_dict method."""
        sorting = UISorting(
            column_name="status",
            sort_order="asc"
        )

        result = sorting.to_dict()
        assert result == {"status": "asc"}

    def test_ui_sorting_to_dict_with_order(self):
        """Test UISorting.to_dict method with custom order."""
        sorting = UISorting(
            column_name="status",
            sort_order="none",
            order=["firing", "resolved"]
        )

        result = sorting.to_dict()
        assert result == {"status": "none", "order": ["firing", "resolved"]}


class TestIncidentTimeouts:
    """Test cases for IncidentTimeouts."""

    def test_incident_timeouts_creation(self):
        """Test creating IncidentTimeouts with valid data."""
        timeouts = IncidentTimeouts(
            firing="6h",
            unknown="1h",
            resolved="12h",
            closed="90d"
        )

        assert timeouts.firing == "6h"
        assert timeouts.unknown == "1h"
        assert timeouts.resolved == "12h"
        assert timeouts.closed == "90d"

    def test_incident_timeouts_defaults(self):
        """Test IncidentTimeouts with default values."""
        timeouts = IncidentTimeouts()

        assert timeouts.firing == "6h"
        assert timeouts.unknown == "6h"
        assert timeouts.resolved == "12h"
        assert timeouts.closed == "90d"

    def test_incident_timeouts_missing_closed(self):
        """Test IncidentTimeouts with missing closed."""
        timeouts = IncidentTimeouts(firing="6h", unknown="1h", resolved="12h")
    
        assert timeouts.closed == "90d"

    def test_incident_timeouts_get_method(self):
        """Test IncidentTimeouts get method."""
        timeouts = IncidentTimeouts(firing="2h")

        assert timeouts.get("firing") == "2h"
        assert timeouts.get("unknown") == "6h"  # Default value


class TestIncidentNotifications:
    """Test cases for IncidentNotifications."""

    def test_incident_notifications_creation(self):
        """Test creating IncidentNotifications with valid data."""
        notifications = IncidentNotifications(
            assignment=True,
            new_firing=False,
            partial_resolved=True
        )

        assert notifications.assignment is True
        assert notifications.new_firing is False
        assert notifications.partial_resolved is True

    def test_incident_notifications_defaults(self):
        """Test IncidentNotifications with default values."""
        notifications = IncidentNotifications()

        assert notifications.assignment is True
        assert notifications.new_firing is True
        assert notifications.partial_resolved is False

    def test_incident_notifications_get_method(self):
        """Test IncidentNotifications get method."""
        notifications = IncidentNotifications(assignment=False)

        assert notifications.get("assignment") is False
        assert notifications.get("new_firing") is True


class TestUserGroup:
    """Test cases for UserGroup."""

    def test_user_group_creation(self):
        """Test creating UserGroup with valid data."""
        group = UserGroup(users=["user1", "user2", "user3"])

        assert group.users == ["user1", "user2", "user3"]


class TestTemplateFiles:
    """Test cases for TemplateFiles."""

    def test_template_files_creation(self):
        """Test creating TemplateFiles with valid data."""
        templates = TemplateFiles(
            status_icons="status_icons.j2",
            header="header.j2",
            body="body.j2"
        )

        assert templates.status_icons == "status_icons.j2"
        assert templates.header == "header.j2"
        assert templates.body == "body.j2"

    def test_template_files_get_method(self):
        """Test TemplateFiles get method."""
        templates = TemplateFiles(status_icons="status.j2")

        assert templates.get("status_icons") == "status.j2"
        assert templates.get("header") is None
        assert templates.get("header", "default.j2") == "default.j2"
