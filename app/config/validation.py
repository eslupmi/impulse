from typing import Dict, List, Optional, Union, Any
try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum
import re
import yaml
import os
from pathlib import Path


class ApplicationType(str, Enum):
    """Supported application types"""
    SLACK = "slack"
    MATTERMOST = "mattermost"
    TELEGRAM = "telegram"


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


class TelegramUser(BaseModel):
    """Telegram user configuration"""
    id: int = Field(..., description="User ID")
    name: Optional[str] = Field(None, description="User display name")
    username: Optional[str] = Field(None, description="Username")


class SlackUser(BaseModel):
    """Slack user configuration"""
    id: str = Field(..., description="User ID")


class MattermostUser(BaseModel):
    """Mattermost user configuration"""
    id: str = Field(..., description="User ID")


class TelegramChannel(BaseModel):
    """Telegram channel configuration"""
    id: int = Field(..., description="Channel ID")
    name: Optional[str] = Field(None, description="Channel name")


class SlackChannel(BaseModel):
    """Slack channel configuration"""
    id: str = Field(..., description="Channel ID")


class MattermostChannel(BaseModel):
    """Mattermost channel configuration"""
    id: str = Field(..., description="Channel ID")


class SimpleChainStep(BaseModel):
    """Base chain step"""
    user: Optional[str] = Field(None, description="User to notify")
    user_group: Optional[str] = Field(None, description="User group to notify")
    webhook: Optional[str] = Field(None, description="Webhook to call")
    chain: Optional[str] = Field(None, description="Nested chain to execute")
    wait: Optional[str] = Field(None, description="Wait duration (e.g., '5m', '1h')")

    @model_validator(mode='after')
    def validate_step_type(self):
        """Validate that exactly one step type is specified"""
        fields = [self.user, self.user_group, self.webhook, self.chain, self.wait]
        non_none_fields = [f for f in fields if f is not None]
        
        if len(non_none_fields) != 1:
            raise ValueError("Exactly one of user, user_group, webhook, chain, or wait must be specified")
        
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


class ScheduleMatcherExpression(BaseModel):
    """Schedule matcher expression - fully flexible"""
    expr: str = Field(..., description="Custom expression")
    start_time: Any = Field(..., description="Start time in any format")
    duration: Any = Field(..., description="Duration in any format")


class ScheduleEntry(BaseModel):
    """Schedule entry configuration"""
    matcher: Optional[List[ScheduleMatcherExpression]] = Field(None, description="List of matcher expressions")
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
    default_steps: Optional[List[SimpleChainStep]] = Field(None, description="Default steps")


class UserGroup(BaseModel):
    """User group configuration"""
    users: List[str] = Field(..., description="List of user names")


class TemplateFiles(BaseModel):
    """Template files configuration"""
    status_icons: Optional[str] = Field(None, description="Status icons template path")
    header: Optional[str] = Field(None, description="Header template path")
    body: Optional[str] = Field(None, description="Body template path")


class ApplicationConfig(BaseModel):
    """Application configuration"""
    type: ApplicationType = Field(..., description="Application type")
    channels: Dict[str, Union[SlackChannel, MattermostChannel, TelegramChannel]] = Field(..., description="Channel definitions")
    users: Dict[str, Union[SlackUser, MattermostUser, TelegramUser]] = Field(..., description="User definitions")
    admin_users: List[str] = Field(..., description="Admin users")
    user_groups: Optional[Dict[str, UserGroup]] = Field(None, description="User groups")
    chains: Optional[Dict[str, Any]] = Field(None, description="Chain definitions")
    
    # Type-specific fields
    address: Optional[str] = Field(None, description="Mattermost server address")
    team: Optional[str] = Field(None, description="Mattermost team name")
    impulse_address: Optional[str] = Field(None, description="Impulse callback address")
    template_files: Optional[TemplateFiles] = Field(None, description="Template files")

    @model_validator(mode='after')
    def validate_type_specific_fields(self):
        """Validate type-specific required fields"""
        if self.type == ApplicationType.MATTERMOST:
            if not self.address:
                raise ValueError("'address' is required for Mattermost")
            if not self.team:
                raise ValueError("'team' is required for Mattermost")
            if not self.impulse_address:
                raise ValueError("'impulse_address' is required for Mattermost")
        
        elif self.type == ApplicationType.TELEGRAM:
            if not self.impulse_address:
                raise ValueError("'impulse_address' is required for Telegram")
        
        return self

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
        
        def validate_chain_steps(steps):
            if not isinstance(steps, list):
                return
            for step in steps:
                if isinstance(step, dict):
                    if 'user' in step and step['user'] and users and step['user'] not in users:
                        raise ValueError(f"User '{step['user']}' in chain not found in users")
                    if 'user_group' in step and step['user_group'] and user_groups and step['user_group'] not in user_groups:
                        raise ValueError(f"User group '{step['user_group']}' in chain not found in user_groups")
                    if 'chain' in step and step['chain'] and step['chain'] not in v:
                        raise ValueError(f"Nested chain '{step['chain']}' not found in chains")
        
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


class IncidentTimeouts(BaseModel):
    """Incident timeout configuration"""
    firing: Optional[str] = Field("6h", description="Firing timeout")
    unknown: Optional[str] = Field("6h", description="Unknown timeout")
    resolved: Optional[str] = Field("12h", description="Resolved timeout")


class IncidentConfig(BaseModel):
    """Incident configuration"""
    alerts_firing_notifications: Optional[bool] = Field(False, description="Enable firing notifications")
    alerts_resolved_notifications: Optional[bool] = Field(False, description="Enable resolved notifications")
    timeouts: Optional[IncidentTimeouts] = Field(None, description="Incident timeouts")


class ExperimentalConfig(BaseModel):
    """Experimental configuration"""
    recreate_chain: Optional[bool] = Field(False, description="Recreate chain on new alerts")


class RouteConfig(BaseModel):
    """Route configuration"""
    channel: str = Field(..., description="Default channel")
    chain: Optional[str] = Field(None, description="Default chain")
    matchers: Optional[List[str]] = Field(None, description="Route matchers")
    routes: Optional[List['RouteConfig']] = Field(None, description="Nested routes")


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


class UIConfig(BaseModel):
    """UI configuration"""
    columns: List[UIColumn] = Field(..., description="Column configurations")
    colors: Optional[Dict[str, Dict[str, str]]] = Field(None, description="Color configurations")
    filters: Optional[List[str]] = Field(None, description="Default filters")
    sorting: Optional[List[Dict[str, Union[str, List[str]]]]] = Field(None, description="Sort rules")

    @field_validator('sorting')
    @classmethod
    def validate_sorting_format(cls, v):
        """Validate sorting format"""
        if v is None:
            return v
        
        for sort_rule in v:
            if not isinstance(sort_rule, dict):
                raise ValueError("Each sorting rule must be a dictionary")
            
            # Each dictionary should have exactly one column name as key
            column_keys = [k for k in sort_rule.keys() if k != 'order']
            if len(column_keys) != 1:
                raise ValueError("Each sorting rule must have exactly one column name as key")
            
            column_name = column_keys[0]
            sort_order = sort_rule[column_name]
            
            if sort_order not in ['asc', 'desc', 'none']:
                raise ValueError(f"Sort order must be 'asc', 'desc', or 'none', got: {sort_order}")
            
            # If sort order is 'none', order field is required
            if sort_order == 'none' and 'order' not in sort_rule:
                raise ValueError("'order' field is required when sort order is 'none'")
        
        return v


class WebhookConfig(BaseModel):
    """Webhook configuration"""
    url: str = Field(..., description="Webhook URL")
    data: Optional[Dict[str, Any]] = Field(None, description="Webhook data")
    auth: Optional[str] = Field(None, description="HTTP Basic Auth")


class ImpulseConfig(BaseModel):
    """Main Impulse configuration"""
    application: ApplicationConfig = Field(..., description="Application configuration")
    incident: Optional[IncidentConfig] = Field(None, description="Incident configuration")
    experimental: Optional[ExperimentalConfig] = Field(None, description="Experimental configuration")
    route: RouteConfig = Field(..., description="Route configuration")
    ui: Optional[UIConfig] = Field(None, description="UI configuration")
    webhooks: Optional[Dict[str, WebhookConfig]] = Field(None, description="Webhook configurations")

    @model_validator(mode='after')
    def validate_route_channel_exists(self):
        """Validate that route channels exist in application channels"""
        def validate_route_channels(route_config):
            if route_config.channel not in self.application.channels:
                raise ValueError(f"Route channel '{route_config.channel}' not found in application channels")
            
            if route_config.routes:
                for nested_route in route_config.routes:
                    validate_route_channels(nested_route)
        
        validate_route_channels(self.route)
        return self

    @model_validator(mode='after')
    def validate_route_chain_exists(self):
        """Validate that route chains exist in application chains"""
        if not self.application.chains:
            return self
        
        chains = self.application.chains
        
        def validate_route_chain(route_config):
            if hasattr(route_config, 'chain') and route_config.chain:
                if route_config.chain not in chains:
                    raise ValueError(f"Route chain '{route_config.chain}' not found in application chains")
            
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