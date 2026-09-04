import re
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, Field, field_validator, model_validator


class MessengerType(str, Enum):
    """Supported messenger types"""
    SLACK = "slack"
    MATTERMOST = "mattermost"
    TELEGRAM = "telegram"
    NONE = "none"


class ChainType(str, Enum):
    """Supported chain types"""
    SCHEDULE = "schedule"
    CLOUD = "cloud"
    UI = "ui"


class CloudProvider(str, Enum):
    """Supported cloud providers"""
    GOOGLE = "google"


class DatetimeFormat(str, Enum):
    """Supported datetime formats"""
    ABSOLUTE = "absolute"
    RELATIVE = "relative"


class SortOrder(str, Enum):
    """Supported sort orders"""
    ASC = "asc"
    DESC = "desc"
    NONE = "none"


class BaseUser(BaseModel):
    def get(self, key: str) -> Any:
        return getattr(self, key)


class TelegramUser(BaseUser):
    """Telegram user configuration"""
    id: int = Field(..., description="User ID")
    name: str | None = Field(None, description="User display name")
    username: str | None = Field(None, description="Username")


class SlackUser(BaseUser):
    """Slack user configuration"""
    id: str = Field(..., description="User ID")


class MattermostUser(BaseUser):
    """Mattermost user configuration"""
    id: str = Field(..., description="User ID")


class TelegramChannel(BaseUser):
    """Telegram channel configuration"""
    id: int = Field(..., description="Channel ID")
    name: str | None = Field(None, description="Channel name")


class SlackChannel(BaseModel):
    """Slack channel configuration"""
    id: str = Field(..., description="Channel ID")


class SlackGroup(BaseModel):
    """Slack group configuration"""
    id: str = Field(..., description="Group ID")


class MattermostChannel(BaseModel):
    """Mattermost channel configuration"""
    id: str = Field(..., description="Channel ID")


class MattermostGroup(BaseModel):
    """Mattermost group configuration"""
    id: str = Field(..., description="Group ID")


class SimpleChainStep(BaseModel):
    """Base chain step"""
    user: str | None = Field(None, description="User to notify")
    user_group: str | None = Field(None, description="User group to notify")
    group: str | None = Field(None, description="Slack group to notify")
    webhook: str | None = Field(None, description="Webhook to call")
    chain: str | None = Field(None, description="Nested chain to execute")
    wait: str | None = Field(None, description="Wait duration (e.g., '5m', '1h')")

    @model_validator(mode='after')
    def validate_step_type(self):
        """Validate that exactly one step type is specified"""
        fields = [self.user, self.user_group, self.group, self.webhook, self.chain, self.wait]
        non_none_fields = [f for f in fields if f is not None]

        if len(non_none_fields) != 1:
            raise ValueError("Exactly one of user, user_group, group, webhook, chain, or wait must be specified")

        return self

    @field_validator('wait')
    @classmethod
    def validate_wait_format(cls, v):
        """Validate wait duration format"""
        if v is None:
            return v

        # Check format like "5m", "1h", "30s", "2d"
        if not re.match(r'^\d+[smhd]$', v):
            raise ValueError("Wait duration must be in format like '5m', '1h', '30s', or '2d'")

        return v

    def get_type_and_value(self) -> tuple[str, str]:
        """Get both type and value of this chain step"""
        for field_name in ['user', 'user_group', 'group', 'webhook', 'chain', 'wait']:
            value = getattr(self, field_name)
            if value is not None:
                return field_name, value
        raise ValueError("SimpleChainStep has no valid type or value set")

    def get_type(self) -> str:
        """Get the type of this chain step"""
        return self.get_type_and_value()[0]

    def get_value(self) -> str:
        """Get the value of this chain step"""
        return self.get_type_and_value()[1]

    def has_chain(self) -> bool:
        """Check if this step references a nested chain"""
        return self.chain is not None


class ScheduleMatcherExpression(BaseModel):
    """Schedule matcher expression - fully flexible"""
    start_day_expr: str = Field(..., description="Start day expression")
    start_day_values: list[Any] = Field(..., description="Start day values")
    start_time: Any = Field(..., description="Start time in any format")
    duration: Any = Field(..., description="Duration in any format")


class ScheduleEntry(BaseModel):
    """Schedule entry configuration"""
    matcher: ScheduleMatcherExpression | None = Field(None, description="Matcher expression")
    steps: list[SimpleChainStep] = Field(..., description="Chain steps")


class SimpleChain(BaseModel):
    """Simple chain configuration - just a list of steps"""
    # This will be handled as List[SimpleChainStep] directly


class ScheduleChain(BaseModel):
    """Schedule chain configuration"""
    type: Literal[ChainType.SCHEDULE] = Field(..., description="Chain type")
    timezone: str = Field("UTC", description="Timezone")
    schedule: list[ScheduleEntry] = Field(..., description="Schedule entries")


class CloudChain(BaseModel):
    """Cloud chain configuration"""
    type: Literal[ChainType.CLOUD] = Field(..., description="Chain type")
    provider: CloudProvider = Field(..., description="Cloud provider")
    calendar_id: str = Field(..., description="Calendar ID")
    default_steps: list[SimpleChainStep] = Field([], description="Default steps")


class UserGroup(BaseModel):
    """User group configuration"""
    users: list[str] = Field(..., description="List of user names")


class TemplateFiles(BaseModel):
    """Template files configuration"""
    status_icons: str | None = Field(None, description="Status icons template path")
    header: str | None = Field(None, description="Header template path")
    body: str | None = Field(None, description="Body template path")

    def get(self, key: str, default: str | None = None) -> str | None:
        return getattr(self, key) or default


class TaskManagementType(str, Enum):
    """Supported task management types"""
    JIRA = "jira"


class TaskManagementTemplateFiles(BaseModel):
    """Task management template files configuration"""
    summary: str | None = Field(None, description="Summary template path")
    description: str | None = Field(None, description="Description template path")

    def get(self, key: str, default: str | None = None) -> str | None:
        return getattr(self, key) or default


class TaskManagementConfig(BaseModel):
    """Task management configuration"""
    type: TaskManagementType = Field(..., description="Task management type")
    project_key: str = Field(..., description="Project key in the task management system")
    template_files: TaskManagementTemplateFiles | None = Field(
        TaskManagementTemplateFiles(summary=None, description=None),
        description="Template files for task creation"
    )


def _validate_simple_chain(chain_config):
    return [SimpleChainStep(**step) for step in chain_config]


def _validate_schedule_chain(chain_config):
    return ScheduleChain(**chain_config)


def _validate_cloud_chain(chain_config):
    return CloudChain(**chain_config)


def _validate_ui_chain(chain_config):
    return chain_config


HttpBase = Annotated[str, AfterValidator(lambda v: v.rstrip("/"))]


class BaseApplicationConfig(BaseModel):
    """Base messenger configuration with common fields"""
    type: MessengerType = Field(..., description="Application type")
    address: HttpBase | None = Field(None, description="Messenger API address")
    impulse_address: HttpBase | None = Field(None, description="Impulse callback address")
    admin_users: list[str] = Field(..., description="Admin users")
    user_groups: dict[str, UserGroup] = Field({}, description="User groups")
    chains: dict[str, Any] = Field({}, description="Chain definitions")
    groups: dict[str, Any] = Field({}, description="Group definitions")
    template_files: TemplateFiles | None = Field(TemplateFiles(status_icons=None, header=None, body=None),
                                                    description="Template files")

    @field_validator('admin_users')
    @classmethod
    def validate_admin_users_exist(cls, v, info):
        """Validate that admin users exist in users"""
        if info.data.get('users'):
            for admin_user in v:
                if admin_user not in info.data['users']:
                    raise ValueError(f"Admin user '{admin_user}' not found in users")
        return v

    @field_validator('chains')
    @classmethod
    def validate_chains_structure_and_references(cls, v, info):
        """Validate chain structure"""
        validated_chains = {}

        for chain_name, chain_config in v.items():
            if isinstance(chain_config, list):
                validated_chains[chain_name] = _validate_simple_chain(chain_config)
            elif isinstance(chain_config, dict):
                chain_type = chain_config.get('type')
                if chain_type == 'schedule':
                    validated_chains[chain_name] = _validate_schedule_chain(chain_config)
                elif chain_type == 'cloud':
                    validated_chains[chain_name] = _validate_cloud_chain(chain_config)
                elif chain_type == 'ui':
                    validated_chains[chain_name] = _validate_ui_chain(chain_config)
                else:
                    raise ValueError(f"Unknown chain type for chain '{chain_name}': {chain_type}")

        return validated_chains


class AddressRequiredApplicationConfig(BaseApplicationConfig):
    """Base for messenger types that require impulse_address"""

    @model_validator(mode='after')
    def validate_impulse_address_required(self):
        if not self.impulse_address:
            raise ValueError(f"messenger.impulse_address is required for {self.type.value}")
        return self


class SlackApplicationConfig(BaseApplicationConfig):
    """Slack messenger configuration"""
    type: Literal[MessengerType.SLACK] = Field(MessengerType.SLACK, description="Application type")
    channels: dict[str, SlackChannel] = Field(..., description="Channel definitions")
    groups: dict[str, SlackGroup] = Field({}, description="Slack group definitions")
    users: dict[str, SlackUser] = Field(..., description="User definitions")


class MattermostApplicationConfig(AddressRequiredApplicationConfig):
    """Mattermost messenger configuration"""
    type: Literal[MessengerType.MATTERMOST] = Field(MessengerType.MATTERMOST, description="Application type")
    channels: dict[str, MattermostChannel] = Field(..., description="Channel definitions")
    groups: dict[str, MattermostGroup] = Field({}, description="Mattermost group definitions")
    users: dict[str, MattermostUser] = Field(..., description="User definitions")
    address: HttpBase = Field(..., description="Mattermost server address")
    team: str = Field(..., description="Mattermost team name")


class TelegramApplicationConfig(AddressRequiredApplicationConfig):
    """Telegram messenger configuration"""
    type: Literal[MessengerType.TELEGRAM] = Field(MessengerType.TELEGRAM, description="Application type")
    channels: dict[str, TelegramChannel] = Field(..., description="Channel definitions")
    users: dict[str, TelegramUser] = Field(..., description="User definitions")


class NullApplicationConfig(BaseApplicationConfig):
    """Null messenger configuration for UI-only mode"""
    type: Literal[MessengerType.NONE] = Field(MessengerType.NONE, description="Application type")
    channels: dict[str, Any] = Field(default_factory=dict, description="Channel definitions (not used)")
    users: dict[str, Any] = Field(default_factory=dict, description="User definitions (not used)")
    admin_users: list[str] = Field(default_factory=list, description="Admin users (not used)")
    impulse_address: str | None = Field(None, description="Impulse callback address (not used)")

    @field_validator('admin_users')
    @classmethod
    def validate_admin_users_exist(cls, v, info):
        """Skip admin users validation for null messenger"""
        return v

    @field_validator('chains')
    @classmethod
    def validate_chains_structure_and_references(cls, v, info):
        """Skip chain validation for null messenger"""
        return v


ApplicationConfig = (
    SlackApplicationConfig | MattermostApplicationConfig | TelegramApplicationConfig | NullApplicationConfig)


class GeneralConfig(BaseModel):
    """General configuration"""
    workday_start: str = Field("09:00", description="Time when workday starts")
    week_start: str = Field("Mon", description="First day of the week")
    timezone: str = Field("UTC", description="Default timezone for freeze calculations")

    @field_validator('workday_start')
    @classmethod
    def validate_workday_start_format(cls, v):
        """Validate workday_start format (HH:MM)"""
        if not re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', v):
            raise ValueError("workday_start must be in HH:MM format (e.g., '09:00')")
        return v

    @field_validator('week_start')
    @classmethod
    def validate_week_start_format(cls, v):
        """Validate week_start format"""
        valid_days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', '0', '1', '2', '3', '4', '5', '6', '7']
        if v not in valid_days:
            raise ValueError(f"week_start must be one of {valid_days}")
        return v


class IncidentTimeouts(BaseModel):
    """Incident timeout configuration"""
    firing: str | None = Field("6h", description="Firing timeout")
    unknown: str | None = Field("6h", description="Unknown timeout")
    resolved: str | None = Field("12h", description="Resolved timeout")
    closed: str | None = Field("90d", description="Closed timeout")

    def get(self, key: str) -> str | None:
        return getattr(self, key) or None


class IncidentNotifications(BaseModel):
    """Incident notification configuration"""
    assignment: bool | None = Field(True, description="Assigned notifications")
    new_firing: bool | None = Field(True, description="New firing notifications")
    partial_resolved: bool | None = Field(True, description="Partial resolved notifications")
    status_update: bool | None = Field(True, description="Status update notifications")
    freeze: bool | None = Field(False, description="Freeze notifications")

    def get(self, key: str) -> bool:
        return getattr(self, key) or False


class IncidentConfig(BaseModel):
    """Incident configuration"""
    notifications: IncidentNotifications | None = Field(IncidentNotifications(), description="Incident timeouts")
    timeouts: IncidentTimeouts | None = Field(None, description="Incident timeouts")


class RouteConfig(BaseModel):
    """Route configuration"""
    channel: str = Field(..., description="Default channel")
    chain: str | None = Field(None, description="Default chain")
    matchers: list[str] = Field([], description="Route matchers")
    routes: list['RouteConfig'] = Field([], description="Nested routes")


class UIColumn(BaseModel):
    """UI column configuration"""
    name: str = Field(..., description="Column name")
    header: str = Field(..., description="Column header")
    value: str = Field(..., description="Column value path")
    type: str | None = Field("string", description="Column type (string, datetime, link, etc.)")
    visible: bool | None = Field(True, description="Column visibility")
    url: str | None = Field(None, description="URL for link type")
    format: str | None = Field("relative", description="Datetime format (absolute, relative)")

    @model_validator(mode='after')
    def validate_link_type(self):
        """Validate link type requirements"""
        if self.type == "link" and not self.url:
            raise ValueError("'url' is required when type is 'link'")
        return self


class UISorting(BaseModel):
    """UI sorting configuration for a single column"""
    column_name: str = Field(..., description="Column name to sort by")
    sort_order: Literal["asc", "desc", "none"] = Field(..., description="Sort order")
    order: list[str] | None = Field(None,
                                       description="Custom order values for sorting (required when sort_order is 'none')")

    @model_validator(mode='after')
    def validate_custom_order(self):
        """Validate that order is provided when sort_order is 'none'"""
        if self.sort_order == "none" and not self.order:
            raise ValueError("'order' field is required when sort_order is 'none'")
        return self

    @classmethod
    def from_dict(cls, sort_dict: dict[str, str | list[str]]) -> "UISorting":
        """Create UISorting from dictionary format used in config"""
        column_keys = [k for k in sort_dict if k != 'order']
        if len(column_keys) != 1:
            raise ValueError("Each sorting rule must have exactly one column name as key")

        column_name = column_keys[0]
        sort_order = sort_dict[column_name]
        order = sort_dict.get('order')

        if sort_order not in ['asc', 'desc', 'none']:
            raise ValueError(f"Sort order must be 'asc', 'desc', or 'none', got: {sort_order}")

        return cls(column_name=column_name, sort_order=sort_order, order=order)


class UIConfig(BaseModel):
    """UI configuration"""
    columns: list[UIColumn] = Field(..., description="Column configurations")
    colors: dict[str, dict[str, str]] | None = Field({}, description="Color configurations")
    filters: list[str] | None = Field([], description="Default filters")
    sorting: list[UISorting] | None = Field([], description="Sort rules")

    @field_validator('sorting', mode='before')
    @classmethod
    def validate_sorting_format(cls, v):
        """Convert dictionary format to UISorting objects"""
        if v is None:
            return v

        if not isinstance(v, list):
            raise TypeError("Sorting must be a list of sort rules")

        sorting_objects = []
        for sort_rule in v:
            if isinstance(sort_rule, dict):
                sorting_objects.append(UISorting.from_dict(sort_rule))
            elif isinstance(sort_rule, UISorting):
                sorting_objects.append(sort_rule)
            else:
                raise TypeError("Each sorting rule must be a dictionary or UISorting object")

        return sorting_objects


class WebhookConfig(BaseModel):
    """Webhook configuration"""
    url: str = Field(..., description="Webhook URL")
    data: dict[str, Any] | None = Field({}, description="Webhook data")
    json_payload: dict[str, Any] | str | None = Field(None, alias="json", description="Webhook JSON payload")
    auth: str | None = Field(None, description="HTTP Basic Auth")

    @model_validator(mode='after')
    def validate_data_json_conflict(self):
        """Validate that data and json are mutually exclusive"""
        has_data = self.data and len(self.data) > 0
        has_json = self.json_payload is not None and (
            (isinstance(self.json_payload, dict) and len(self.json_payload) > 0) or 
            (isinstance(self.json_payload, str) and len(self.json_payload.strip()) > 0)
        )
        
        if has_data and has_json:
            raise ValueError("Cannot specify both 'data' and 'json' fields - use one or the other")
        
        return self


class InhibitRule(BaseModel):
    """Single inhibition rule configuration for AlertManager-style inhibition"""
    source_matchers: list[str] = Field(..., description="Source matchers (e.g., 'severity =~ \"critical\"')")
    target_matchers: list[str] = Field(..., description="Target matchers (e.g., 'severity =~ \"warning\"')")
    equal: list[str] = Field([], description="Labels that must be equal between source and target")


class ImpulseConfig(BaseModel):
    """Main Impulse configuration"""
    general: GeneralConfig = Field(default_factory=GeneralConfig, description="General configuration")
    messenger: ApplicationConfig = Field(..., description="Messenger configuration", discriminator='type')
    incident: IncidentConfig | None = Field(None, description="Incident configuration")
    route: RouteConfig | None = Field(None, description="Route configuration")
    ui: UIConfig | None = Field(None, description="UI configuration")
    webhooks: dict[str, WebhookConfig] = Field({}, description="Webhook configurations")
    task_management: TaskManagementConfig | None = Field(None, description="Task management configuration")
    inhibit_rules: list[InhibitRule] = Field([], description="Inhibition rules for AlertManager-style inhibition")

    @model_validator(mode='after')
    def validate_route_exists(self):
        """Validate that route exists"""

        def validate_route(route_config: RouteConfig):
            if not route_config:
                raise ValueError(f"'route' field is required when type is {self.messenger.type.value}")

        if self.messenger.type != MessengerType.NONE:
            validate_route(self.route)
        return self

    @model_validator(mode='after')
    def validate_route_channel_exists(self):
        """Validate that route channels exist in messenger channels"""

        def validate_route_channels(route_config):
            if route_config.channel not in self.messenger.channels:
                raise ValueError(f"Route channel '{route_config.channel}' not found in messenger channels")

            if route_config.routes:
                for nested_route in route_config.routes:
                    validate_route_channels(nested_route)

        if self.messenger.type != MessengerType.NONE:
            validate_route_channels(self.route)
        return self

    @model_validator(mode='after')
    def validate_route_chain_exists(self):
        """Validate that route chains exist in messenger chains"""
        if not self.messenger.chains:
            return self

        chains = self.messenger.chains

        def validate_route_chain(route_config: RouteConfig):
            if route_config.chain and route_config.chain not in chains:
                raise ValueError(f"Route chain '{route_config.chain}' not found in messenger chains")

            if route_config.routes:
                for nested_route in route_config.routes:
                    validate_route_chain(nested_route)

        if self.route is not None:
            validate_route_chain(self.route)
        return self


# Update forward references
RouteConfig.model_rebuild()


def validate_config(config_dict: dict) -> ImpulseConfig:
    """
    Validate configuration dictionary using Pydantic models.
    
    Args:
        config_dict: Dictionary containing configuration data
        
    Returns:
        ImpulseConfig: Validated configuration object
        
    Raises:
        pydantic.ValidationError: If validation fails
    """
    return ImpulseConfig(**config_dict)
