"""Reglas y utilidades de dominio para pagos."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.error_codes import (
    FIELD_NOT_FOUND,
    PAYMENT_INVALID_STATUS,
    PAYMENT_MISSING_APPROVAL_CODE,
    PAYMENT_MISSING_PAYER_PHONE,
    PAYMENT_MISSING_RENT_ID,
    PAYMENT_RECEIVER_NOT_CONFIGURED,
    RENT_NOT_FOUND,
    http_error,
)
from app.integrations import (
    AuthReaderError,
    get_payment_destination,
    get_rent_context,
    get_user_summary,
)


def normalize_status(value: Optional[str]) -> str:
    """Normaliza el status de pago.

    Usado por: PaymentService.create_payment/update_payment.
    """
    return (value or "").strip().lower()


def validate_status(status_value: str, *, allowed_statuses: list[str]) -> None:
    """Valida que el status esté permitido.

    Usado por: PaymentService.create_payment/update_payment.
    """
    allowed = set(allowed_statuses)
    if not status_value or status_value not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise http_error(
            PAYMENT_INVALID_STATUS,
            detail=f"Invalid payment status '{status_value}'. Allowed: {allowed_list}",
        )


def ensure_paid_at(status_value: str, payment_data: dict) -> None:
    """Asigna paid_at si el status es paid y no fue provisto.

    Usado por: PaymentService.create_payment/update_payment.
    """
    if status_value == "paid" and not payment_data.get("paid_at"):
        payment_data["paid_at"] = datetime.now(timezone.utc)


def apply_yape_plin_context(
    db: Session,
    payment_data: dict,
    *,
    rent_id: Optional[int],
    payer_phone: Optional[str],
    approval_code: Optional[str],
) -> None:
    """Completa metadata para pagos Yape/Plin.

    Usado por: PaymentService.create_payment.
    """
    if rent_id is None:
        raise http_error(
            PAYMENT_MISSING_RENT_ID,
            detail="rent_id is required for Yape/Plin payments",
        )
    if not payer_phone:
        raise http_error(
            PAYMENT_MISSING_PAYER_PHONE,
            detail="payer_phone is required for Yape/Plin payments",
        )
    if not approval_code:
        raise http_error(
            PAYMENT_MISSING_APPROVAL_CODE,
            detail="approval_code is required for Yape/Plin payments",
        )

    rent_context = get_rent_context(db, rent_id)
    if rent_context is None:
        raise http_error(
            RENT_NOT_FOUND,
            detail="Rent not found for payment",
        )
    if rent_context.field_id is None:
        raise http_error(
            FIELD_NOT_FOUND,
            detail="Rent does not include a field identifier",
        )

    destination = get_payment_destination(db, rent_context.field_id)
    if destination is None:
        raise http_error(
            FIELD_NOT_FOUND,
            detail="Field/campus not found for payment",
        )

    receiver_phone = None
    receiver_name = None
    if destination.manager_id is not None:
        try:
            manager = get_user_summary(db, destination.manager_id)
        except AuthReaderError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to reach auth service for campus manager",
            ) from exc

        if manager is not None and manager.phone:
            receiver_phone = manager.phone
            receiver_name = f"{manager.name} {manager.lastname}".strip()

    if not receiver_phone:
        receiver_phone = destination.business_phone
        receiver_name = receiver_name or destination.business_name

    if not receiver_phone:
        raise http_error(
            PAYMENT_RECEIVER_NOT_CONFIGURED,
            detail="No payment receiver configured for the campus",
        )

    metadata = merge_additional_data(
        payment_data.get("additional_data"),
        {
            "channel": payment_data.get("method"),
            "payer_phone": payer_phone,
            "approval_code": approval_code,
            "receiver_phone": receiver_phone,
            "receiver_name": receiver_name,
            "campus_id": destination.campus_id,
            "campus_name": destination.campus_name,
            "field_id": destination.field_id,
            "rent_id": rent_context.rent_id,
            "schedule_id": rent_context.schedule_id,
        },
    )

    payment_data["additional_data"] = json.dumps(metadata, ensure_ascii=True)
    if payment_data.get("reference") is None:
        payment_data["reference"] = approval_code


def merge_additional_data(existing: Optional[str], updates: dict) -> dict:
    """Fusiona metadata existente con nuevos campos.

    Usado por: apply_yape_plin_context.
    """
    if not existing:
        return dict(updates)

    try:
        payload = json.loads(existing)
    except json.JSONDecodeError:
        payload = {"client_notes": existing}

    if not isinstance(payload, dict):
        payload = {"client_notes": existing}

    payload.update(updates)
    return payload


__all__ = [
    "normalize_status",
    "validate_status",
    "ensure_paid_at",
    "apply_yape_plin_context",
    "merge_additional_data",
]
