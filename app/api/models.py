import re

from pydantic import AwareDatetime, BaseModel, StrictStr, field_validator


class AssignmentRequest(BaseModel):
    user_id: StrictStr


class FreezeRequest(BaseModel):
    until: AwareDatetime

    @field_validator("until", mode="before")
    @classmethod
    def require_rfc3339(cls, value):
        if not isinstance(value, str) or not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})", value,
        ):
            raise ValueError("until must be an RFC3339 string")
        return value
