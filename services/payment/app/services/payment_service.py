"""Business logic for managing payments."""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repository import payment_repository
from app.schemas.payment import PaymentCreate, PaymentUpdate


class PaymentService:
    def __init__(self, db: Session):
        self.db = db

    def list_payments(self, *, status_filter: Optional[str] = None):
        return payment_repository.list_payments(
            self.db, status_filter=status_filter
        )

    def get_payment(self, payment_id: int):
        payment = payment_repository.get_payment(self.db, payment_id)
        if payment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found",
            )
        return payment

    def create_payment(self, payload: PaymentCreate):
        payment_data = payload.dict(exclude_unset=True)
        payment = payment_repository.create_payment(self.db, payment_data)
        return payment

    def update_payment(self, payment_id: int, payload: PaymentUpdate):
        payment = self.get_payment(payment_id)
        update_data = payload.dict(exclude_unset=True)

        if not update_data:
            return payment

        # Apply only the provided fields so callers can send partial updates
        # (e.g., just status/receipt) without re-sending the full object.
        for field, value in update_data.items():
            setattr(payment, field, value)

        return payment_repository.save_payment(self.db, payment)


__all__ = ["PaymentService"]
