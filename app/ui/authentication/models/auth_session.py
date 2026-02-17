from datetime import datetime

from pydantic import BaseModel

from app.ui.authentication.models.auth_user import AuthUser


class AuthSession(BaseModel):
    session_id: str
    user: AuthUser
    created_at: datetime
    expires_at: datetime
