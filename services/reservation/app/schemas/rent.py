"""Pydantic schemas for rent resources."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.schedule import FieldSummary, UserSummary


class RentBase(BaseModel):
    period: str = Field(..., max_length=20)
    start_time: datetime
    end_time: datetime
    initialized: Optional[datetime]
    finished: Optional[datetime]
    status: str = Field(..., max_length=30)
    id_status: Optional[int] = None
    minutes: Decimal
    mount: Decimal
    date_log: datetime
    date_create: Optional[datetime] = None
    payment_deadline: datetime
    capacity: int
    id_payment: Optional[int] = None
    payment_code: Optional[str] = Field(None, max_length=30)
    payment_proof_url: Optional[str] = None
    payment_reviewed_at: Optional[datetime] = None
    payment_reviewed_by: Optional[int] = None
    customer_full_name: Optional[str] = Field(None, max_length=200)
    customer_phone: Optional[str] = Field(None, max_length=20)
    customer_email: Optional[str] = Field(None, max_length=200)
    customer_document: Optional[str] = Field(None, max_length=30)
    customer_notes: Optional[str] = None
    id_schedule: Optional[int] = None


class RentCreate(BaseModel):
    """Schema used when creating a new rent."""

    id_schedule: int = Field(..., gt=0)
    id_payment: Optional[int] = Field(None, gt=0)
    status: str = Field(..., max_length=30)
    id_status: Optional[int] = None
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
    customer_full_name: Optional[str] = Field(None, max_length=200)
    customer_phone: Optional[str] = Field(None, max_length=20)
    customer_email: Optional[str] = Field(None, max_length=200)
    customer_document: Optional[str] = Field(None, max_length=30)
    customer_notes: Optional[str] = None
    payment_code: Optional[str] = Field(None, max_length=30)
    payment_proof_url: Optional[str] = None
    payment_reviewed_at: Optional[datetime] = None
    payment_reviewed_by: Optional[int] = None


class RentCreateCombo(BaseModel):
    """Create a single rent covering multiple fields (combined courts)."""

    id_combination: int = Field(..., gt=0)
    id_schedules: List[int] = Field(..., min_length=2)
    id_payment: Optional[int] = Field(None, gt=0)
    status: str = Field(..., max_length=30)
    id_status: Optional[int] = None
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
    customer_full_name: Optional[str] = Field(None, max_length=200)
    customer_phone: Optional[str] = Field(None, max_length=20)
    customer_email: Optional[str] = Field(None, max_length=200)
    customer_document: Optional[str] = Field(None, max_length=30)
    customer_notes: Optional[str] = None
    payment_code: Optional[str] = Field(None, max_length=30)
    payment_proof_url: Optional[str] = None
    payment_reviewed_at: Optional[datetime] = None
    payment_reviewed_by: Optional[int] = None


class RentAdminCreate(BaseModel):
    """Schema used when creating a new rent by admin."""

    id_schedule: int = Field(..., gt=0)
    status: str = Field(..., max_length=30)
    id_status: Optional[int] = None
    id_payment: Optional[int] = Field(None, gt=0)
    customer_full_name: str = Field(..., max_length=200)
    customer_phone: Optional[str] = Field(None, max_length=20)
    customer_email: Optional[str] = Field(None, max_length=200)
    customer_document: Optional[str] = Field(None, max_length=30)
    customer_notes: Optional[str] = None
    payment_code: Optional[str] = Field(None, max_length=30)
    payment_proof_url: Optional[str] = None
    payment_reviewed_at: Optional[datetime] = None
    payment_reviewed_by: Optional[int] = None


class RentUpdate(BaseModel):
    """Schema used when updating an existing rent."""

    period: Optional[str] = Field(None, max_length=20)
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    initialized: Optional[datetime]
    finished: Optional[datetime]
    status: Optional[str] = Field(None, max_length=30)
    id_status: Optional[int] = None
    minutes: Optional[Decimal]
    mount: Optional[Decimal]
    date_log: Optional[datetime]
    date_create: Optional[datetime]
    payment_deadline: Optional[datetime]
    capacity: Optional[int]
    id_payment: Optional[int]
    id_schedule: Optional[int]
    customer_full_name: Optional[str] = Field(None, max_length=200)
    customer_phone: Optional[str] = Field(None, max_length=20)
    customer_email: Optional[str] = Field(None, max_length=200)
    customer_document: Optional[str] = Field(None, max_length=30)
    customer_notes: Optional[str] = None
    payment_code: Optional[str] = Field(None, max_length=30)
    payment_proof_url: Optional[str] = None
    payment_reviewed_at: Optional[datetime] = None
    payment_reviewed_by: Optional[int] = None


class RentAdminUpdate(BaseModel):
    """Schema used when updating a rent by admin."""

    id_schedule: Optional[int] = Field(None, gt=0)
    status: Optional[str] = Field(None, max_length=30)
    id_status: Optional[int] = None
    id_payment: Optional[int] = Field(None, gt=0)
    customer_full_name: Optional[str] = Field(None, max_length=200)
    customer_phone: Optional[str] = Field(None, max_length=20)
    customer_email: Optional[str] = Field(None, max_length=200)
    customer_document: Optional[str] = Field(None, max_length=30)
    customer_notes: Optional[str] = None
    payment_code: Optional[str] = Field(None, max_length=30)
    payment_proof_url: Optional[str] = None
    payment_reviewed_at: Optional[datetime] = None
    payment_reviewed_by: Optional[int] = None


class ScheduleSummary(BaseModel):
    """Schedule information included when returning rents."""

    id_schedule: int
    day_of_week: str
    start_time: datetime
    end_time: datetime
    status: str
    id_status: Optional[int] = None
    price: Decimal
    field: FieldSummary
    user: Optional[UserSummary] = None

    class Config:
        from_attributes = True


class RentResponse(RentBase):
    """Rent data returned to API clients."""

    id_rent: int
    schedules: List[ScheduleSummary]
    schedule: ScheduleSummary

    class Config:
        from_attributes = True


class PaymentInstructions(BaseModel):
    yape_phone: Optional[str] = None
    yape_qr_url: Optional[str] = None
    plin_phone: Optional[str] = None
    plin_qr_url: Optional[str] = None
    payment_code: str
    message: str
    status: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class RentPaymentResponse(BaseModel):
    rent: RentResponse
    payment_instructions: PaymentInstructions


class RentCancelRequest(BaseModel):
    schedule_id: Optional[int] = Field(None, gt=0)


class RentCancelResponse(BaseModel):
    rent_id: Optional[int] = None
    rent_status: Optional[str] = None
    schedule_id: int
    schedule_status: str
