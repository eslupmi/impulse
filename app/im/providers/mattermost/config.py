from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.im.plugin_api import BaseApplicationConfig, BaseUser, HttpBase, MessengerType


class MattermostUser(BaseUser):
    id: str


class MattermostChannel(BaseModel):
    id: str


class MattermostGroup(BaseModel):
    id: str


class MattermostApplicationConfig(BaseApplicationConfig):
    """Mattermost messenger configuration"""
    type: Literal[MessengerType.MATTERMOST] = Field(MessengerType.MATTERMOST, description="Application type")
    channels: dict[str, MattermostChannel] = Field(..., description="Channel definitions")
    groups: dict[str, MattermostGroup] = Field({}, description="Mattermost group definitions")
    users: dict[str, MattermostUser] = Field(..., description="User definitions")
    address: HttpBase = Field(..., description="Mattermost server address")
    team: str = Field(..., description="Mattermost team name")

    @model_validator(mode='after')
    def validate_impulse_address_required(self):
        if not self.impulse_address:
            raise ValueError(f"messenger.impulse_address is required for {self.type.value}")
        return self
