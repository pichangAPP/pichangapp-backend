"""Pydantic models for payment resources."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class PaymentBase(BaseModel):
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(..., max_length=30)
    method: str = Field(..., max_length=100)
    status: str = Field(..., max_length=30)
    type: str = Field(..., max_length=30)
    paid_at: Optional[datetime] = None
    memberships_id_membership: int = Field(..., ge=1)
    reference: Optional[str] = Field(None, max_length=100)
    additional_data: Optional[str] = None


class PaymentCreate(PaymentBase):
    rent_id: Optional[int] = Field(
        None,
        ge=1,
        description="Rent identifier used to resolve the campus for Yape/Plin payments.",
    )
    payer_phone: Optional[str] = Field(
        None,
        max_length=20,
        description="Phone number used by the user to pay via Yape/Plin.",
    )
    approval_code: Optional[str] = Field(
        None,
        max_length=100,
        description="Approval code reported by Yape/Plin.",
    )


class PaymentUpdate(BaseModel):
    amount: Optional[Decimal] = Field(None, gt=0)
    currency: Optional[str] = Field(None, max_length=30)
    method: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = Field(None, max_length=30)
    type: Optional[str] = Field(None, max_length=30)
    paid_at: Optional[datetime] = None
    memberships_id_membership: Optional[int] = Field(None, ge=1)
    reference: Optional[str] = Field(None, max_length=100)
    additional_data: Optional[str] = None


class PaymentResponse(PaymentBase):
    id_payment: int
    transaction_id: int
    paid_at: datetime

    class Config:
        from_attributes = True


__all__ = [
    "PaymentBase",
    "PaymentCreate",
    "PaymentUpdate",
    "PaymentResponse",
]
