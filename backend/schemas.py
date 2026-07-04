from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, HttpUrl, field_validator


class UrlCreate(BaseModel):
    url: HttpUrl


class CheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url_id: int
    status_code: Optional[int]
    response_time_ms: Optional[float]
    is_up: bool
    checked_at: datetime

    @field_validator("checked_at", mode="after")
    @classmethod
    def ensure_checked_at_tz_aware(cls, v: datetime) -> datetime:
        if v and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v


class UrlResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    created_at: datetime

    @field_validator("created_at", mode="after")
    @classmethod
    def ensure_created_at_tz_aware(cls, v: datetime) -> datetime:
        if v and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v


class UrlWithLatestCheck(UrlResponse):
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    is_up: Optional[bool] = None
    checked_at: Optional[datetime] = None
    recent_checks: list[CheckResponse] = []

    @field_validator("checked_at", mode="after")
    @classmethod
    def ensure_latest_checked_at_tz_aware(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v



class HealthResponse(BaseModel):
    status: str

