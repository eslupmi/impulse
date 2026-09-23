"""Public configuration schema shared by internally registered providers."""
import re
from enum import Enum
from typing import Annotated, Any, Literal
from pydantic import AfterValidator, BaseModel, Field, field_validator, model_validator

HttpBase = Annotated[str, AfterValidator(lambda v: v.rstrip("/"))]

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

class BaseUser(BaseModel):
    def get(self, key: str) -> Any:
        return getattr(self, key)

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

def _validate_simple_chain(chain_config):
    return [SimpleChainStep(**step) for step in chain_config]

def _validate_schedule_chain(chain_config):
    return ScheduleChain(**chain_config)

def _validate_cloud_chain(chain_config):
    return CloudChain(**chain_config)

def _validate_ui_chain(chain_config):
    return chain_config

class BaseApplicationConfig(BaseModel):
    """Base messenger configuration with common fields"""
    type: MessengerType = Field(..., description="Application type")
    impulse_address: HttpBase | None = Field(None, description="Impulse callback address")
    admin_users: list[str] = Field(..., description="Admin users")
    user_groups: dict[str, UserGroup] = Field({}, description="User groups")
    chains: dict[str, Any] = Field({}, description="Chain definitions")
    groups: dict[str, Any] = Field({}, description="Group definitions")
    template_files: TemplateFiles | None = Field(TemplateFiles(status_icons=None, header=None, body=None),
                                                    description="Template files")

    channels: dict[str, Any] = Field(default_factory=dict)
    users: dict[str, Any] = Field(default_factory=dict)

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
