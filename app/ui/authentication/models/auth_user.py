from typing import Optional

from pydantic import BaseModel


class AuthUser(BaseModel):
    id: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    timezone: Optional[str] = None
    messenger: str
