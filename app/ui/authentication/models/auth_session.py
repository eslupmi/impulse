from datetime import datetime

from pydantic import BaseModel


class AuthSession(BaseModel):
    session_id: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    cookie_path: str = "/"
