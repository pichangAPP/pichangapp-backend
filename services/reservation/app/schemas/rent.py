"""Pydantic schemas for rent resources."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class RentBase(BaseModel):
    period: str = Field(..., max_length=20)
    start_time: datetime
    end_time: datetime
    initialized: datetime
    finished: datetime
    status: str = Field(..., max_length=30)
    minutes: Decimal
    mount: Decimal
    date_log: datetime
    date_create: Optional[datetime] = None
    capacity: int
    id_payment: int
    id_schedule: int


class RentCreate(RentBase):
    """Schema used when creating a new rent."""

    pass


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
    capacity: Optional[int]
    id_payment: Optional[int]
    id_schedule: Optional[int]


class RentResponse(RentBase):
    """Rent data returned to API clients."""

    id_rent: int

    class Config:
        orm_mode = True
