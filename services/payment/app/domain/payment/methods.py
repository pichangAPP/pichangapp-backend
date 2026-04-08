"""Reglas y utilidades de dominio para métodos de pago."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.core.error_codes import (
    PAYMENT_METHODS_EXISTS,
    PAYMENT_METHODS_INVALID,
    http_error,
)


def validate_method_requirements(data: dict) -> None:
    """Valida campos requeridos según los métodos habilitados.

    Usado por: PaymentMethodsService.create/update.
    """
    requirements = {
        "uses_yape": ["yape_phone", "yape_qr_url"],
        "uses_plin": ["plin_phone", "plin_qr_url"],
        "uses_bank_transfer": [
            "bank_name",
            "account_currency",
            "account_number",
            "cci",
            "account_holder_name",
            "account_holder_doc",
        ],
        "uses_card": ["card_provider", "merchant_id", "terminal_id", "public_key"],
        "uses_pos": ["pos_provider", "pos_detail"],
        "uses_apple_pay": ["apple_pay_provider", "apple_pay_merchant_id"],
        "uses_google_pay": ["google_pay_provider", "google_pay_merchant_id"],
        "uses_invoice": ["invoice_detail"],
    }

    for method_flag, required_fields in requirements.items():
        if not data.get(method_flag):
            continue

        missing_fields = [
            field_name
            for field_name in required_fields
            if data.get(field_name) in (None, "")
        ]
        if missing_fields:
            raise http_error(
                PAYMENT_METHODS_INVALID,
                detail=(
                    f"{', '.join(missing_fields)} are required when "
                    f"{method_flag} is true"
                ),
            )


def current_state(payment_methods) -> dict:
    """Convierte el modelo actual en dict para validaciones.

    Usado por: PaymentMethodsService.update.
    """
    return {
        "id_business": payment_methods.id_business,
        "id_campus": payment_methods.id_campus,
        "uses_cash": payment_methods.uses_cash,
        "uses_yape": payment_methods.uses_yape,
        "yape_phone": payment_methods.yape_phone,
        "yape_qr_url": payment_methods.yape_qr_url,
        "uses_plin": payment_methods.uses_plin,
        "plin_phone": payment_methods.plin_phone,
        "plin_qr_url": payment_methods.plin_qr_url,
        "uses_bank_transfer": payment_methods.uses_bank_transfer,
        "bank_name": payment_methods.bank_name,
        "account_currency": payment_methods.account_currency,
        "account_number": payment_methods.account_number,
        "cci": payment_methods.cci,
        "account_holder_name": payment_methods.account_holder_name,
        "account_holder_doc": payment_methods.account_holder_doc,
        "uses_card": payment_methods.uses_card,
        "card_provider": payment_methods.card_provider,
        "merchant_id": payment_methods.merchant_id,
        "terminal_id": payment_methods.terminal_id,
        "public_key": payment_methods.public_key,
        "uses_pos": payment_methods.uses_pos,
        "pos_provider": payment_methods.pos_provider,
        "pos_detail": payment_methods.pos_detail,
        "uses_apple_pay": payment_methods.uses_apple_pay,
        "apple_pay_provider": payment_methods.apple_pay_provider,
        "apple_pay_merchant_id": payment_methods.apple_pay_merchant_id,
        "uses_google_pay": payment_methods.uses_google_pay,
        "google_pay_provider": payment_methods.google_pay_provider,
        "google_pay_merchant_id": payment_methods.google_pay_merchant_id,
        "uses_invoice": payment_methods.uses_invoice,
        "invoice_detail": payment_methods.invoice_detail,
        "extra": payment_methods.extra,
        "status": payment_methods.status,
    }


def map_integrity_error(exc: IntegrityError) -> HTTPException:
    """Mapea errores de integridad a mensajes de negocio.

    Usado por: PaymentMethodsService.create/update.
    """
    detail = str(exc.orig).lower()
    if "uq_payment_methods_business_campus" in detail or (
        "duplicate key value" in detail and "id_business" in detail and "id_campus" in detail
    ):
        return http_error(
            PAYMENT_METHODS_EXISTS,
            detail="Payment methods configuration already exists for this business/campus",
        )

    if "chk_" in detail:
        return http_error(
            PAYMENT_METHODS_INVALID,
            detail="Payment methods validation failed due to check constraints",
        )

    return http_error(
        PAYMENT_METHODS_INVALID,
        detail="Invalid payment methods payload",
    )


__all__ = ["validate_method_requirements", "current_state", "map_integrity_error"]
