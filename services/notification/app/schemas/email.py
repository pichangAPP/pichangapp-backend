"""Schemas for incoming email notifications."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class Person(BaseModel):
    name: str = Field(..., max_length=200)
    lastname: str = Field(..., max_length=200)
    email: EmailStr


class CampusSummary(BaseModel):
    id_campus: int
    name: str = Field(..., max_length=300)
    address: str
    district: str = Field(..., max_length=200)


class RentDetails(BaseModel):
    rent_id: int
    schedule_day: str = Field(..., max_length=30)
    start_time: datetime
    end_time: datetime
    status: str = Field(..., max_length=30)
    period: str = Field(..., max_length=20)
    mount: Decimal
    payment_deadline: datetime
    field_name: str = Field(..., max_length=200)
    campus: CampusSummary


class NotificationRequest(BaseModel):
    rent: RentDetails
    user: Person
    manager: Optional[Person] = None


__all__ = ["NotificationRequest", "RentDetails", "Person", "CampusSummary"]
