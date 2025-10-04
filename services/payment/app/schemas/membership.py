"""Pydantic schemas for membership resources."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class MembershipBase(BaseModel):
    membership_name: str
    price: float
    duration: int
    status: str = "active"
    detail: Optional[str] = None


class MembershipCreate(MembershipBase):
    date_payments: Optional[datetime] = None


class MembershipUpdate(BaseModel):
    membership_name: Optional[str] = None
    price: Optional[float] = None
    duration: Optional[int] = None
    status: Optional[str] = None
    detail: Optional[str] = None
    date_payments: Optional[datetime] = None


class MembershipResponse(MembershipBase):
    model_config = ConfigDict(from_attributes=True)

    id_membership: int
    creation_date: datetime
    date_payments: Optional[datetime] = None
