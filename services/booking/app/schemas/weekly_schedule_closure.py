from __future__ import annotations

from datetime import datetime, time
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class WeeklyScheduleClosureBase(BaseModel):
    """weekday: Python convention Monday=0 .. Sunday=6."""

    id_field: Optional[int] = Field(
        default=None,
        gt=0,
        description="If set, rule applies only to this field; if null, entire campus.",
    )
    weekday: int = Field(..., ge=0, le=6)
    local_start_time: Optional[time] = None
    local_end_time: Optional[time] = None
    reason: Optional[str] = Field(default=None, max_length=500)
    is_active: bool = True


class WeeklyScheduleClosureCreate(WeeklyScheduleClosureBase):
    pass


class WeeklyScheduleClosureUpdate(BaseModel):
    id_field: Optional[int] = Field(default=None, gt=0)
    weekday: Optional[int] = Field(default=None, ge=0, le=6)
    local_start_time: Optional[time] = None
    local_end_time: Optional[time] = None
    reason: Optional[str] = Field(default=None, max_length=500)
    is_active: Optional[bool] = None


class WeeklyScheduleClosureResponse(WeeklyScheduleClosureBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_campus: int
    created_at: datetime
    updated_at: Optional[datetime] = None
