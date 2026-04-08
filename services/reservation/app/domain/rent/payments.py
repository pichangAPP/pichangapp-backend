"""Payment helpers for rent workflows."""
from __future__ import annotations

import secrets
import string
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.error_codes import PAYMENT_NOT_FOUND, http_error
from app.integrations import payment_reader
from app.models.rent import Rent
from app.schemas.rent import PaymentInstructions
from app.schemas.schedule import FieldSummary


def generate_payment_code(length: int = 6) -> str:
    """Generate a short payment code for rent instructions.

    Used by: RentService.create_rent when a payment_code is not provided.
    """
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def build_payment_instructions(
    db: Session,
    rent: Rent,
    *,
    field_summary: Optional[FieldSummary],
) -> PaymentInstructions:
    """Build payment instructions including campus wallet details when available.

    Used by: RentService.create_rent and create_rent_admin responses.
    """
    wallet_info = None
    if field_summary is not None:
        wallet_info = payment_reader.get_campus_digital_wallets(
            db, campus_id=field_summary.id_campus
        )

    if not wallet_info:
        return PaymentInstructions(
            payment_code=rent.payment_code or "",
            message="Realiza el pago y sube la captura para continuar.",
        )

    has_yape = bool(wallet_info.get("yape_phone") or wallet_info.get("yape_qr_url"))
    has_plin = bool(wallet_info.get("plin_phone") or wallet_info.get("plin_qr_url"))
    if has_yape and has_plin:
        message = "Realiza el pago por Yape o Plin y sube la captura para continuar."
    elif has_yape:
        message = "Realiza el pago por Yape y sube la captura para continuar."
    elif has_plin:
        message = "Realiza el pago por Plin y sube la captura para continuar."
    else:
        message = "Realiza el pago y sube la captura para continuar."

    return PaymentInstructions(
        yape_phone=wallet_info.get("yape_phone") if has_yape else None,
        yape_qr_url=wallet_info.get("yape_qr_url") if has_yape else None,
        plin_phone=wallet_info.get("plin_phone") if has_plin else None,
        plin_qr_url=wallet_info.get("plin_qr_url") if has_plin else None,
        payment_code=rent.payment_code or "",
        message=message,
        status=wallet_info.get("status"),
        created_at=wallet_info.get("created_at"),
        updated_at=wallet_info.get("updated_at"),
    )


def validate_payment(db: Session, payment_id: int) -> None:
    """Ensure the payment exists and is in paid status.

    Used by: RentService.create_rent/update_rent when linking payments.
    """
    payment_status = payment_reader.get_payment_status(db, payment_id)
    if payment_status is None:
        raise http_error(
            PAYMENT_NOT_FOUND,
            detail="Associated payment not found",
        )

    status_value = (payment_status or "").lower()
    if status_value != "paid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment must be in paid status to link with the rent",
        )


__all__ = ["generate_payment_code", "build_payment_instructions", "validate_payment"]
