from datetime import datetime

from pydantic import BaseModel


class AuthState(BaseModel):
    state: str
    next_path: str
    created_at: datetime
