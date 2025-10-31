"""Pydantic schemas for rent resources."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.schedule import FieldSummary, UserSummary


class RentBase(BaseModel):
    period: str = Field(..., max_length=20)
    start_time: datetime
    end_time: datetime
    initialized: Optional[datetime]
    finished: Optional[datetime]
    status: str = Field(..., max_length=30)
    minutes: Decimal
    mount: Decimal
    date_log: datetime
    date_create: Optional[datetime] = None
    payment_deadline: datetime
    capacity: int
    id_payment: Optional[int] = None
    id_schedule: int


class RentCreate(BaseModel):
    """Schema used when creating a new rent."""

    id_schedule: int = Field(..., gt=0)
    id_payment: Optional[int] = Field(None, gt=0)
    status: str = Field(..., max_length=30)
    period: Optional[str] = Field(None, max_length=20)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    initialized: Optional[datetime] = None
    finished: Optional[datetime] = None
    minutes: Optional[Decimal] = None
    mount: Optional[Decimal] = None
    date_log: Optional[datetime] = None
    date_create: Optional[datetime] = None
    capacity: Optional[int] = Field(None, ge=0)


class RentUpdate(BaseModel):
    """Schema used when updating an existing rent."""

    period: Optional[str] = Field(None, max_length=20)
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    initialized: Optional[datetime]
    finished: Optional[datetime]
    status: Optional[str] = Field(None, max_length=30)
    minutes: Optional[Decimal]
    mount: Optional[Decimal]
    date_log: Optional[datetime]
    date_create: Optional[datetime]
    payment_deadline: Optional[datetime]
    capacity: Optional[int]
    id_payment: Optional[int]
    id_schedule: Optional[int]


class ScheduleSummary(BaseModel):
    """Schedule information included when returning rents."""

    id_schedule: int
    day_of_week: str
    start_time: datetime
    end_time: datetime
    status: str
    price: Decimal
    field: FieldSummary
    user: UserSummary

    class Config:
        orm_mode = True


class RentResponse(RentBase):
    """Rent data returned to API clients."""

    id_rent: int
    schedule: ScheduleSummary

    class Config:
        orm_mode = True
