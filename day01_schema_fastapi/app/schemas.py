from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RuntimeSchema(BaseModel):
    """Shared validation behavior for data entering the runtime."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        str_strip_whitespace=True,
    )


class DeviceStatusSchema(RuntimeSchema):
    device_id: str = Field(min_length=3, description="Unique device identifier")
    region: str = Field(min_length=1, description="Device region, such as south_china")
    android_version: str = Field(min_length=1)
    firmware_version: str = Field(min_length=1)
    online: bool
    error_code: str | None = None
    failure_rate_7d: float = Field(ge=0, le=1)
    last_seen_at: datetime = Field(strict=False)


class ElderlyRecordSchema(RuntimeSchema):
    elder_id: str = Field(min_length=1, description="Unique elderly record identifier")
    age: int = Field(ge=0, le=120)
    systolic_bp: int = Field(ge=0)
    diastolic_bp: int = Field(ge=0)
    has_chronic_disease: bool
    latest_alert: str | None = None
    updated_at: datetime = Field(strict=False)


class OTTQuerySchema(RuntimeSchema):
    query_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    query_text: str = Field(min_length=5)
    channel: Literal["web", "tv", "miniapp"]
    include_history: bool = False
    max_results: int = Field(default=5, ge=1, le=20)
