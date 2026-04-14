"""Notificaciones push por usuario (lee tokens en auth.user_devices)."""

from __future__ import annotations

import logging
from sqlalchemy.orm import Session

from app.domain.notification.fcm import is_unregistered_fcm_error, send_push
from app.repository.push_token_repository import (
    deactivate_token_globally,
    list_active_push_tokens,
)

logger = logging.getLogger(__name__)


def notify_user(
    db: Session,
    id_user: int,
    *,
    title: str,
    body: str,
    data: dict[str, str],
) -> list[str]:
    """Envía a todos los tokens activos del usuario. Devuelve message_ids exitosos."""
    tokens = list_active_push_tokens(db, id_user)
    if not tokens:
        return []
    message_ids: list[str] = []
    for token in tokens:
        try:
            mid = send_push(token, title, body, data)
            message_ids.append(mid)
        except Exception as exc:  # noqa: BLE001 — errores FCM heterogéneos
            if is_unregistered_fcm_error(exc):
                logger.info("FCM token inválido; desactivando: %s", token[:16])
                deactivate_token_globally(db, token)
            else:
                logger.warning("FCM send falló para usuario %s: %s", id_user, exc)
    return message_ids


def notify_user_from_event(
    db: Session,
    *,
    id_user: int | None,
    event_type: str,
    rent_id: int,
    schedule_day: str,
    status: str,
) -> None:
    """Mapea eventos de reserva a título/cuerpo y data string para la app."""
    if not id_user:
        return
    data = {
        "type": "rent",
        "event_type": event_type,
        "rent_id": str(rent_id),
        "schedule_day": schedule_day,
        "status": status,
    }
    if event_type == "rent.payment_received":
        title = "Pago registrado"
        body = "Recibimos tu pago. Tu reserva está en revisión."
    elif event_type in {"rent.verdict", "rent.approved", "rent.rejected"}:
        title = "Actualización de reserva"
        body = f"Estado: {status}. Toca para ver detalles."
    else:
        title = "Cuadra"
        body = "Tienes una actualización de reserva."
    notify_user(db, id_user, title=title, body=body, data=data)


__all__ = ["notify_user", "notify_user_from_event"]
