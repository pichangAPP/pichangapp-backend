"""Construcción de contexto y formatos para emails de notificación."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from app.core.config import settings
from app.schemas import NotificationRequest
from app.domain.notification.templates import build_status_context


def humanize_rent_status(status_value: str) -> str:
    """Etiqueta legible del estado para boleta y correo."""
    key = (status_value or "").strip().lower()
    mapping = {
        "under_review": "Pago en revisión",
        "reserved": "Confirmada",
        "pending_payment": "Pago pendiente",
        "pending_proof": "Falta evidencia de pago",
        "proof_submitted": "Evidencia recibida",
        "needs_info": "Se requiere información adicional",
        "cancelled": "Cancelada",
        "fullfilled": "Completada",
        "expired_no_proof": "Expirada (sin evidencia)",
        "expired_slot_unavailable": "Expirada (sin disponibilidad)",
        "dispute_open": "En disputa",
        "dispute_resolved": "Disputa resuelta",
        "rejected_not_received": "Rechazada (pago no recibido)",
        "rejected_invalid_proof": "Rechazada (evidencia inválida)",
        "rejected_amount_low": "Rechazada (monto incompleto)",
        "rejected_amount_high": "Rechazada (monto excedente)",
        "rejected_wrong_destination": "Rechazada (destino incorrecto)",
    }
    if key.startswith("rejected_") and key not in mapping:
        return "Rechazada"
    return mapping.get(key, (status_value or "").replace("_", " ").title())


def format_datetime(value: datetime) -> str:
    """Formatea fechas con zona horaria cuando está presente.

    Usado por: build_common_context.
    """
    if value.tzinfo:
        return value.strftime("%d/%m/%Y %H:%M %Z")
    return value.strftime("%d/%m/%Y %H:%M")


def format_decimal(value: Decimal) -> str:
    """Formatea montos con separador decimal local.

    Usado por: build_common_context.
    """
    return f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def format_minutes_wait_display(value: Optional[Decimal]) -> Optional[str]:
    """Texto legible para booking.field.minutes_wait (minutos de anticipación)."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v < 0:
        v = 0.0
    if abs(v - round(v)) < 1e-6:
        n = int(round(v))
        return f"{n} minutos"
    text = f"{v:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") + " minutos"


def build_common_context(payload: NotificationRequest) -> Dict[str, Any]:
    """Construye el contexto base para renderizar plantillas.

    Usado por: EmailService.send_rent_notification/send_user_confirmation.
    """
    rent = payload.rent
    campus = rent.campus
    status_context = build_status_context(rent.status)
    context: Dict[str, Any] = {
        "rent": rent,
        "user": payload.user,
        "manager": payload.manager,
        "campus": campus,
        "field_name": rent.field_name,
        "date_range": f"{format_datetime(rent.start_time)} - {format_datetime(rent.end_time)}",
        "start_time_display": format_datetime(rent.start_time),
        "end_time_display": format_datetime(rent.end_time),
        "payment_deadline_display": format_datetime(rent.payment_deadline),
        "amount_display": format_decimal(rent.mount),
        "rent_status_label": humanize_rent_status(rent.status),
        "app_brand": settings.APP_BRAND_NAME,
        "minutes_wait_display": format_minutes_wait_display(rent.minutes_wait),
    }
    context.update(status_context)
    return context


__all__ = [
    "build_common_context",
    "format_datetime",
    "format_decimal",
    "format_minutes_wait_display",
    "humanize_rent_status",
]
