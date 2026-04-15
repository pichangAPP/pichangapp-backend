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
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(None, max_length=50)


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
    # booking.field.minutes_wait (anticipo antes del turno). Opcional por payloads antiguos.
    minutes_wait: Optional[Decimal] = Field(None, ge=0)
    campus: CampusSummary


class NotificationRequest(BaseModel):
    rent: RentDetails
    user: Person
    manager: Optional[Person] = None
    # Cliente autenticado (schedule.id_user); ausente en reservas invitado.
    id_user: Optional[int] = Field(None, gt=0)


__all__ = [
    "NotificationRequest",
    "RentDetails",
    "Person",
    "CampusSummary",
]
