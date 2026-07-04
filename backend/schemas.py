from datetime import datetime, timezone
from typing import Annotated, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, HttpUrl


def make_utc(v: Optional[datetime]) -> Optional[datetime]:
    if v and v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


UtcDateTime = Annotated[datetime, BeforeValidator(make_utc)]
OptionalUtcDateTime = Annotated[Optional[datetime], BeforeValidator(make_utc)]


class UrlCreate(BaseModel):
    url: HttpUrl


class CheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url_id: int
    status_code: Optional[int]
    response_time_ms: Optional[float]
    is_up: bool
    checked_at: UtcDateTime


class UrlResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    created_at: UtcDateTime


class UrlWithLatestCheck(UrlResponse):
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    is_up: Optional[bool] = None
    checked_at: OptionalUtcDateTime = None
    recent_checks: list[CheckResponse] = []


class HealthResponse(BaseModel):
    status: str
