"""Database helpers for payment methods persistence."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.payment_methods import PaymentMethods


def list_payment_methods(
    db: Session,
    *,
    id_business: Optional[int] = None,
    id_campus: Optional[int] = None,
    status_filter: Optional[str] = None,
) -> list[PaymentMethods]:
    query = db.query(PaymentMethods)

    if id_business is not None:
        query = query.filter(PaymentMethods.id_business == id_business)
    if id_campus is not None:
        query = query.filter(PaymentMethods.id_campus == id_campus)
    if status_filter is not None:
        query = query.filter(PaymentMethods.status == status_filter)

    return query.order_by(PaymentMethods.id_payment_methods.desc()).all()


def get_payment_methods(db: Session, payment_methods_id: int) -> Optional[PaymentMethods]:
    return (
        db.query(PaymentMethods)
        .filter(PaymentMethods.id_payment_methods == payment_methods_id)
        .first()
    )


def get_payment_methods_by_business_campus(
    db: Session,
    *,
    id_business: int,
    id_campus: int,
) -> Optional[PaymentMethods]:
    return (
        db.query(PaymentMethods)
        .filter(
            PaymentMethods.id_business == id_business,
            PaymentMethods.id_campus == id_campus,
        )
        .first()
    )


def create_payment_methods(db: Session, payload: dict) -> PaymentMethods:
    payment_methods = PaymentMethods(**payload)
    db.add(payment_methods)
    db.flush()
    db.commit()
    db.refresh(payment_methods)
    return payment_methods


def save_payment_methods(db: Session, payment_methods: PaymentMethods) -> PaymentMethods:
    db.flush()
    db.commit()
    db.refresh(payment_methods)
    return payment_methods


def delete_payment_methods(db: Session, payment_methods: PaymentMethods) -> None:
    db.delete(payment_methods)
    db.flush()
    db.commit()


__all__ = [
    "list_payment_methods",
    "get_payment_methods",
    "get_payment_methods_by_business_campus",
    "create_payment_methods",
    "save_payment_methods",
    "delete_payment_methods",
]
