"""Notificaciones push por usuario (lee tokens en auth.user_devices)."""

from __future__ import annotations

import logging
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain.notification.fcm import is_unregistered_fcm_error, send_push
from app.repository.push_token_repository import (
    deactivate_token_globally,
    list_active_push_tokens,
)

logger = logging.getLogger(__name__)


def _push_message_for_status(status: str) -> tuple[str, str]:
    normalized = (status or "").strip().lower()
    if normalized == "under_review":
        return ("Pago en revision", "Recibimos tu pago. Tu reserva esta en revision.")
    if normalized == "reserved":
        return ("Reserva confirmada", "Tu reserva fue confirmada. Toca para ver detalles.")
    if normalized == "pending_payment":
        return ("Pago pendiente", "Tu reserva sigue pendiente de pago.")
    if normalized == "pending_proof":
        return ("Falta evidencia", "Sube tu comprobante para continuar con la reserva.")
    if normalized == "proof_submitted":
        return ("Evidencia recibida", "Recibimos tu comprobante. Pronto validaremos el pago.")
    if normalized == "needs_info":
        return (
            "Mas informacion requerida",
            "Necesitamos datos adicionales para validar tu pago.",
        )
    if normalized == "cancelled":
        return ("Reserva cancelada", "Tu reserva fue cancelada.")
    if normalized == "fullfilled":
        return ("Reserva completada", "Tu reserva fue completada. Gracias por jugar.")
    if normalized == "expired_no_proof":
        return ("Reserva expirada", "La reserva expiro por falta de evidencia de pago.")
    if normalized == "expired_slot_unavailable":
        return ("Reserva expirada", "El horario ya no estaba disponible para tu reserva.")
    if normalized == "dispute_open":
        return ("Caso en revision", "Se abrio un caso para tu reserva.")
    if normalized == "dispute_resolved":
        return ("Caso resuelto", "El caso de tu reserva fue resuelto.")
    if normalized.startswith("rejected_"):
        return ("Reserva rechazada", f"Estado: {status}. Toca para ver detalles.")
    return ("Actualizacion de reserva", f"Estado: {status}. Toca para ver detalles.")


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


def _get_campus_manager_id(db: Session, id_campus: int | None) -> int | None:
    if not id_campus:
        return None
    result = db.execute(
        text(
            """
            SELECT id_manager
            FROM booking.campus
            WHERE id_campus = :id_campus
            LIMIT 1
            """
        ),
        {"id_campus": int(id_campus)},
    )
    row = result.first()
    if row is None:
        return None
    manager_id = row[0]
    return int(manager_id) if manager_id is not None else None


def notify_user_from_event(
    db: Session,
    *,
    id_user: int | None,
    id_campus: int | None,
    event_type: str,
    rent_id: int,
    schedule_day: str,
    status: str,
) -> None:
    """Mapea eventos de reserva a título/cuerpo y data string para la app."""
    data = {
        "type": "rent",
        "event_type": event_type,
        "rent_id": str(rent_id),
        "schedule_day": schedule_day,
        "status": status,
    }
    if id_user:
        if event_type == "rent.payment_received":
            title, body = ("Pago registrado", "Recibimos tu pago. Tu reserva esta en revision.")
        else:
            title, body = _push_message_for_status(status)
        notify_user(db, id_user, title=title, body=body, data=data)

    manager_id = _get_campus_manager_id(db, id_campus)
    if manager_id is None or manager_id == id_user:
        return

    manager_title = "Actividad en tu campus"
    manager_body = f"Nueva actualizacion de reserva ({status}) en {schedule_day}."
    manager_data = dict(data)
    manager_data["target_role"] = "manager"
    notify_user(
        db,
        manager_id,
        title=manager_title,
        body=manager_body,
        data=manager_data,
    )


__all__ = ["notify_user", "notify_user_from_event"]
