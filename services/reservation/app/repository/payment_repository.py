"""Helpers to interact with payment records from the reservation service."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.payment import Payment


def get_payment(db: Session, payment_id: int) -> Optional[Payment]:
    """Fetch a payment by its identifier."""

    return db.query(Payment).filter(Payment.id_payment == payment_id).first()


__all__ = ["get_payment"]
