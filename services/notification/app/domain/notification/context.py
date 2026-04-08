"""Construcción de contexto y formatos para emails de notificación."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict

from app.schemas import NotificationRequest
from app.domain.notification.templates import build_status_context


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
    }
    context.update(status_context)
    return context


__all__ = ["build_common_context", "format_datetime", "format_decimal"]
