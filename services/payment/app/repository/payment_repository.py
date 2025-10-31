"""Database helpers for payment persistence."""

from __future__ import annotations

from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models.payment import Payment


def list_payments(db: Session, *, status_filter: Optional[str] = None) -> list[Payment]:
    query = db.query(Payment)

    if status_filter is not None:
        query = query.filter(Payment.status == status_filter)

    return query.order_by(Payment.paid_at.desc()).all()


def get_payment(db: Session, payment_id: int) -> Optional[Payment]:
    return db.query(Payment).filter(Payment.id_payment == payment_id).first()


def create_payment(db: Session, payment_data: Dict[str, object]) -> Payment:
    payment = Payment(**payment_data)
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def save_payment(db: Session, payment: Payment) -> Payment:
    db.flush()
    db.commit()
    db.refresh(payment)
    return payment


__all__ = [
    "list_payments",
    "get_payment",
    "create_payment",
    "save_payment",
]
