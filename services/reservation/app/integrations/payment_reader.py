"""Read-only access to payment schema data."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_payment_status(db: Session, payment_id: int) -> Optional[str]:
    query = text(
        """
        SELECT status
        FROM payment.payment
        WHERE id_payment = :payment_id
        """
    )
    return db.execute(query, {"payment_id": payment_id}).scalar_one_or_none()


__all__ = ["get_payment_status"]
