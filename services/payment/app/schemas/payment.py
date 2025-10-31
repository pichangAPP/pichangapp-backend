"""Pydantic models for payment resources."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class PaymentBase(BaseModel):
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(..., max_length=30)
    method: str = Field(..., max_length=100)
    status: str = Field(..., max_length=30)
    type: str = Field(..., max_length=30)
    paid_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    memberships_id_membership: int = Field(..., ge=1)
    reference: Optional[str] = Field(None, max_length=100)
    additional_data: Optional[str] = None


class PaymentCreate(PaymentBase):
    pass


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

    class Config:
        orm_mode = True


__all__ = [
    "PaymentBase",
    "PaymentCreate",
    "PaymentUpdate",
    "PaymentResponse",
]
