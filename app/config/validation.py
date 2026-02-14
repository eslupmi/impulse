import os
import re
from enum import Enum
from typing import Dict, List, Optional, Union, Any
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


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
    name: Optional[str] = Field(None, description="User display name")
    username: Optional[str] = Field(None, description="Username")


class SlackUser(BaseUser):
    """Slack user configuration"""
    id: str = Field(..., description="User ID")


class MattermostUser(BaseUser):
    """Mattermost user configuration"""
    id: str = Field(..., description="User ID")


class TelegramChannel(BaseUser):
    """Telegram channel configuration"""
    id: int = Field(..., description="Channel ID")
    name: Optional[str] = Field(None, description="Channel name")


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
    user: Optional[str] = Field(None, description="User to notify")
    user_group: Optional[str] = Field(None, description="User group to notify")
    group: Optional[str] = Field(None, description="Slack group to notify")
    webhook: Optional[str] = Field(None, description="Webhook to call")
    chain: Optional[str] = Field(None, description="Nested chain to execute")
    wait: Optional[str] = Field(None, description="Wait duration (e.g., '5m', '1h')")

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
    start_day_values: List[Any] = Field(..., description="Start day values")
    start_time: Any = Field(..., description="Start time in any format")
    duration: Any = Field(..., description="Duration in any format")


class ScheduleEntry(BaseModel):
    """Schedule entry configuration"""
    matcher: Optional[ScheduleMatcherExpression] = Field(None, description="Matcher expression")
    steps: List[SimpleChainStep] = Field(..., description="Chain steps")


class SimpleChain(BaseModel):
    """Simple chain configuration - just a list of steps"""
    pass  # This will be handled as List[SimpleChainStep] directly


class ScheduleChain(BaseModel):
    """Schedule chain configuration"""
    type: Literal[ChainType.SCHEDULE] = Field(..., description="Chain type")
    timezone: Optional[str] = Field("UTC", description="Timezone")
    schedule: List[ScheduleEntry] = Field(..., description="Schedule entries")


class CloudChain(BaseModel):
    """Cloud chain configuration"""
    type: Literal[ChainType.CLOUD] = Field(..., description="Chain type")
    provider: CloudProvider = Field(..., description="Cloud provider")
    calendar_id: str = Field(..., description="Calendar ID")
    default_steps: Optional[List[SimpleChainStep]] = Field([], description="Default steps")


class UserGroup(BaseModel):
    """User group configuration"""
    users: List[str] = Field(..., description="List of user names")


class TemplateFiles(BaseModel):
    """Template files configuration"""
    status_icons: Optional[str] = Field(None, description="Status icons template path")
    header: Optional[str] = Field(None, description="Header template path")
    body: Optional[str] = Field(None, description="Body template path")

    def get(self, key: str, default: str = None) -> str:
        return getattr(self, key) or default


class TaskManagementType(str, Enum):
    """Supported task management types"""
    JIRA = "jira"


class TaskManagementTemplateFiles(BaseModel):
    """Task management template files configuration"""
    summary: Optional[str] = Field(None, description="Summary template path")
    description: Optional[str] = Field(None, description="Description template path")

    def get(self, key: str, default: str = None) -> str:
        return getattr(self, key) or default


class TaskManagementConfig(BaseModel):
    """Task management configuration"""
    type: TaskManagementType = Field(..., description="Task management type")
    project_key: str = Field(..., description="Project key in the task management system")
    template_files: Optional[TaskManagementTemplateFiles] = Field(
        TaskManagementTemplateFiles(summary=None, description=None),
        description="Template files for task creation"
    )


class BaseApplicationConfig(BaseModel):
    """Base messenger configuration with common fields"""
    type: MessengerType = Field(..., description="Application type")
    admin_users: List[str] = Field(..., description="Admin users")
    user_groups: Optional[Dict[str, UserGroup]] = Field({}, description="User groups")
    chains: Optional[Dict[str, Any]] = Field({}, description="Chain definitions")
    template_files: Optional[TemplateFiles] = Field(TemplateFiles(status_icons=None, header=None, body=None),
                                                    description="Template files")

    @field_validator('admin_users')
    @classmethod
    def validate_admin_users_exist(cls, v, info):
        """Validate that admin users exist in users"""
        if 'users' in info.data and info.data['users']:
            for admin_user in v:
                if admin_user not in info.data['users']:
                    raise ValueError(f"Admin user '{admin_user}' not found in users")
        return v

    @field_validator('chains')
    @classmethod
    def validate_chains_structure_and_references(cls, v, info):
        """Validate chain structure and references"""
        if v is None:
            return v

        users = info.data.get('users', {})
        user_groups = info.data.get('user_groups', {})
        groups = info.data.get('groups', {})

        def validate_chain_steps(steps):
            if not isinstance(steps, list):
                return
            for step_ in steps:
                if isinstance(step_, dict):
                    if 'user' in step_ and step_['user'] and users and step_['user'] not in users:
                        raise ValueError(f"User '{step_['user']}' in chain not found in users")
                    if 'user_group' in step_ and step_['user_group'] and user_groups and step_[
                        'user_group'] not in user_groups:
                        raise ValueError(f"User group '{step_['user_group']}' in chain not found in user_groups")
                    if 'group' in step_ and step_['group'] and groups and step_['group'] not in groups:
                        raise ValueError(f"Group '{step_['group']}' in chain not found in groups")
                    if 'chain' in step_ and step_['chain'] and step_['chain'] not in v:
                        raise ValueError(f"Nested chain '{step_['chain']}' not found in chains")

        validated_chains = {}

        for chain_name, chain_config in v.items():
            if isinstance(chain_config, list):
                # Simple chain - validate steps
                validated_steps = []
                for step in chain_config:
                    validated_steps.append(SimpleChainStep(**step))
                validated_chains[chain_name] = validated_steps
                validate_chain_steps(chain_config)

            elif isinstance(chain_config, dict):
                if chain_config.get('type') == 'schedule':
                    # Schedule chain
                    validated_chains[chain_name] = ScheduleChain(**chain_config)
                    if 'schedule' in chain_config:
                        for schedule_entry in chain_config['schedule']:
                            if isinstance(schedule_entry, dict) and 'steps' in schedule_entry:
                                validate_chain_steps(schedule_entry['steps'])

                elif chain_config.get('type') == 'cloud':
                    # Cloud chain
                    validated_chains[chain_name] = CloudChain(**chain_config)
                    if 'default_steps' in chain_config:
                        validate_chain_steps(chain_config['default_steps'])

                else:
                    raise ValueError(f"Unknown chain type for chain '{chain_name}': {chain_config.get('type')}")

        return validated_chains


class SlackApplicationConfig(BaseApplicationConfig):
    """Slack messenger configuration"""
    type: Literal[MessengerType.SLACK] = Field(MessengerType.SLACK, description="Application type")
    channels: Dict[str, SlackChannel] = Field(..., description="Channel definitions")
    groups: Optional[Dict[str, SlackGroup]] = Field({}, description="Slack group definitions")
    users: Dict[str, SlackUser] = Field(..., description="User definitions")


class MattermostApplicationConfig(BaseApplicationConfig):
    """Mattermost messenger configuration"""
    type: Literal[MessengerType.MATTERMOST] = Field(MessengerType.MATTERMOST, description="Application type")
    channels: Dict[str, MattermostChannel] = Field(..., description="Channel definitions")
    groups: Optional[Dict[str, MattermostGroup]] = Field({}, description="Mattermost group definitions")
    users: Dict[str, MattermostUser] = Field(..., description="User definitions")
    address: str = Field(..., description="Mattermost server address")
    team: str = Field(..., description="Mattermost team name")
    impulse_address: str = Field(..., description="Impulse callback address")


class TelegramApplicationConfig(BaseApplicationConfig):
    """Telegram messenger configuration"""
    type: Literal[MessengerType.TELEGRAM] = Field(MessengerType.TELEGRAM, description="Application type")
    channels: Dict[str, TelegramChannel] = Field(..., description="Channel definitions")
    users: Dict[str, TelegramUser] = Field(..., description="User definitions")
    impulse_address: str = Field(..., description="Impulse callback address")
    address: Optional[str] = Field(None, description="Telegram API address (optional)")


class NullApplicationConfig(BaseApplicationConfig):
    """Null messenger configuration for UI-only mode"""
    type: Literal[MessengerType.NONE] = Field(MessengerType.NONE, description="Application type")
    channels: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Channel definitions (not used)")
    users: Optional[Dict[str, Any]] = Field(default_factory=dict, description="User definitions (not used)")
    admin_users: List[str] = Field(default_factory=list, description="Admin users (not used)")

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


# Union type for all messenger configurations
ApplicationConfig = Union[
    SlackApplicationConfig, MattermostApplicationConfig, TelegramApplicationConfig, NullApplicationConfig]


class GeneralConfig(BaseModel):
    """General configuration"""
    workday_start: Optional[str] = Field("09:00", description="Time when workday starts")
    week_start: Optional[str] = Field("Mon", description="First day of the week")
    timezone: Optional[str] = Field("UTC", description="Default timezone for freeze calculations")

    @field_validator('workday_start')
    @classmethod
    def validate_workday_start_format(cls, v):
        """Validate workday_start format (HH:MM)"""
        if v and not re.match(r'^([01]\d|2[0-3]):([0-5]\d)$', v):
            raise ValueError("workday_start must be in HH:MM format (e.g., '09:00')")
        return v

    @field_validator('week_start')
    @classmethod
    def validate_week_start_format(cls, v):
        """Validate week_start format"""
        valid_days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', '0', '1', '2', '3', '4', '5', '6', '7']
        if v and v not in valid_days:
            raise ValueError(f"week_start must be one of {valid_days}")
        return v


class IncidentTimeouts(BaseModel):
    """Incident timeout configuration"""
    firing: Optional[str] = Field("6h", description="Firing timeout")
    unknown: Optional[str] = Field("6h", description="Unknown timeout")
    resolved: Optional[str] = Field("12h", description="Resolved timeout")
    closed: Optional[str] = Field("90d", description="Closed timeout")

    def get(self, key: str) -> str:
        return getattr(self, key) or None


class IncidentNotifications(BaseModel):
    """Incident notification configuration"""
    assignment: Optional[bool] = Field(True, description="Assigned notifications")
    new_firing: Optional[bool] = Field(True, description="New firing notifications")
    partial_resolved: Optional[bool] = Field(True, description="Partial resolved notifications")
    status_update: Optional[bool] = Field(True, description="Status update notifications")

    def get(self, key: str) -> bool:
        return getattr(self, key) or False


class IncidentConfig(BaseModel):
    """Incident configuration"""
    notifications: Optional[IncidentNotifications] = Field(IncidentNotifications(), description="Incident timeouts")
    timeouts: Optional[IncidentTimeouts] = Field(None, description="Incident timeouts")


class RouteConfig(BaseModel):
    """Route configuration"""
    channel: str = Field(..., description="Default channel")
    chain: Optional[str] = Field(None, description="Default chain")
    matchers: Optional[List[str]] = Field([], description="Route matchers")
    routes: Optional[List['RouteConfig']] = Field([], description="Nested routes")


class UIColumn(BaseModel):
    """UI column configuration"""
    name: str = Field(..., description="Column name")
    header: str = Field(..., description="Column header")
    value: str = Field(..., description="Column value path")
    type: Optional[str] = Field("string", description="Column type (string, datetime, link, etc.)")
    visible: Optional[bool] = Field(True, description="Column visibility")
    url: Optional[str] = Field(None, description="URL for link type")
    format: Optional[str] = Field("relative", description="Datetime format (absolute, relative)")

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
    order: Optional[List[str]] = Field(None,
                                       description="Custom order values for sorting (required when sort_order is 'none')")

    @model_validator(mode='after')
    def validate_custom_order(self):
        """Validate that order is provided when sort_order is 'none'"""
        if self.sort_order == "none" and not self.order:
            raise ValueError("'order' field is required when sort_order is 'none'")
        return self

    @classmethod
    def from_dict(cls, sort_dict: Dict[str, Union[str, List[str]]]) -> "UISorting":
        """Create UISorting from dictionary format used in config"""
        column_keys = [k for k in sort_dict.keys() if k != 'order']
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
    columns: List[UIColumn] = Field(..., description="Column configurations")
    colors: Optional[Dict[str, Dict[str, str]]] = Field({}, description="Color configurations")
    filters: Optional[List[str]] = Field([], description="Default filters")
    sorting: Optional[List[UISorting]] = Field([], description="Sort rules")

    @field_validator('sorting', mode='before')
    @classmethod
    def validate_sorting_format(cls, v):
        """Convert dictionary format to UISorting objects"""
        if v is None:
            return v

        if not isinstance(v, list):
            raise ValueError("Sorting must be a list of sort rules")

        sorting_objects = []
        for sort_rule in v:
            if isinstance(sort_rule, dict):
                sorting_objects.append(UISorting.from_dict(sort_rule))
            elif isinstance(sort_rule, UISorting):
                sorting_objects.append(sort_rule)
            else:
                raise ValueError("Each sorting rule must be a dictionary or UISorting object")

        return sorting_objects


class WebhookConfig(BaseModel):
    """Webhook configuration"""
    url: str = Field(..., description="Webhook URL")
    data: Optional[Dict[str, Any]] = Field({}, description="Webhook data")
    json_payload: Optional[Union[Dict[str, Any], str]] = Field(None, alias="json", description="Webhook JSON payload")
    auth: Optional[str] = Field(None, description="HTTP Basic Auth")

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
    source_matchers: List[str] = Field(..., description="Source matchers (e.g., 'severity =~ \"critical\"')")
    target_matchers: List[str] = Field(..., description="Target matchers (e.g., 'severity =~ \"warning\"')")
    equal: Optional[List[str]] = Field([], description="Labels that must be equal between source and target")


class ImpulseConfig(BaseModel):
    """Main Impulse configuration"""
    general: Optional[GeneralConfig] = Field(GeneralConfig(), description="General configuration")
    messenger: ApplicationConfig = Field(..., description="Messenger configuration", discriminator='type')
    incident: Optional[IncidentConfig] = Field(None, description="Incident configuration")
    route: Optional[RouteConfig] = Field(None, description="Route configuration")
    ui: Optional[UIConfig] = Field(None, description="UI configuration")
    webhooks: Optional[Dict[str, WebhookConfig]] = Field({}, description="Webhook configurations")
    task_management: Optional[TaskManagementConfig] = Field(None, description="Task management configuration")
    inhibit_rules: Optional[List[InhibitRule]] = Field([], description="Inhibition rules for AlertManager-style inhibition")

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

        def validate_route_chain(route_config):
            if hasattr(route_config, 'chain') and route_config.chain:
                if route_config.chain not in chains:
                    raise ValueError(f"Route chain '{route_config.chain}' not found in messenger chains")

            if hasattr(route_config, 'routes') and route_config.routes:
                for nested_route in route_config.routes:
                    validate_route_chain(nested_route)

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


def validate_config_file(config_path: str) -> ImpulseConfig:
    """
    Load and validate configuration from YAML file.
    
    Args:
        config_path: Path to the YAML configuration file
        
    Returns:
        ImpulseConfig: Validated configuration object
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML parsing fails
        pydantic.ValidationError: If validation fails
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as file:
        config_dict = yaml.safe_load(file)

    return validate_config(config_dict)
