

from pydantic import BaseModel


class AuthUser(BaseModel):
    id: str
    username: str | None = None
    full_name: str | None = None
    email: str | None = None
    timezone: str | None = None
    messenger: str
