"""Business logic for managing payments."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.error_codes import PAYMENT_NOT_FOUND, http_error
from app.domain.payment.payments import (
    apply_yape_plin_context,
    ensure_paid_at,
    normalize_status,
    validate_status,
)
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
            raise http_error(
                PAYMENT_NOT_FOUND,
                detail="Payment not found",
            )
        return payment

    def create_payment(self, payload: PaymentCreate):
        payment_data = payload.model_dump(exclude_unset=True)
        method = (payment_data.get("method") or "").strip().lower()
        status_value = normalize_status(payment_data.get("status"))
        validate_status(status_value, allowed_statuses=list(settings.payment_allowed_statuses))
        payment_data["status"] = status_value

        rent_id = payment_data.pop("rent_id", None)
        payer_phone = payment_data.pop("payer_phone", None)
        approval_code = payment_data.pop("approval_code", None)

        if method in {"yape", "plin"}:
            apply_yape_plin_context(
                self.db,
                payment_data,
                rent_id=rent_id,
                payer_phone=payer_phone,
                approval_code=approval_code,
            )

        ensure_paid_at(status_value, payment_data)

        payment = payment_repository.create_payment(self.db, payment_data)
        return payment

    def update_payment(self, payment_id: int, payload: PaymentUpdate):
        payment = self.get_payment(payment_id)
        update_data = payload.model_dump(exclude_unset=True)

        if not update_data:
            return payment

        if "status" in update_data:
            status_value = normalize_status(update_data.get("status"))
            validate_status(status_value, allowed_statuses=list(settings.payment_allowed_statuses))
            update_data["status"] = status_value
            ensure_paid_at(status_value, update_data)

        # Apply only the provided fields so callers can send partial updates
        # (e.g., just status/receipt) without re-sending the full object.
        for field, value in update_data.items():
            setattr(payment, field, value)

        return payment_repository.save_payment(self.db, payment)

__all__ = ["PaymentService"]
