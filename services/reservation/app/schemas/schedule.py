"""Pydantic schemas for schedule resources."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class ScheduleBase(BaseModel):
    day_of_week: str = Field(..., max_length=30)
    start_time: datetime
    end_time: datetime
    status: str = Field(..., max_length=30)
    price: Decimal
    id_field: int
    id_user: int


class ScheduleCreate(ScheduleBase):
    """Schema used when creating a new schedule."""

    pass


class ScheduleUpdate(BaseModel):
    """Schema used when updating an existing schedule."""

    day_of_week: Optional[str] = Field(None, max_length=30)
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    status: Optional[str] = Field(None, max_length=30)
    price: Optional[Decimal]
    id_field: Optional[int]
    id_user: Optional[int]


class ScheduleResponse(ScheduleBase):
    """Schedule data returned to API clients."""

    id_schedule: int

    class Config:
        orm_mode = True
