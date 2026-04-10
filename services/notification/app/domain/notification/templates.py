"""Selección de plantillas y mensajes de estado para notificaciones."""
from __future__ import annotations

from typing import Dict

from app.core.config import settings


def select_user_templates(status_value: str) -> tuple[str, str]:
    """Selecciona plantillas para el usuario.

    Usado por: EmailService.send_rent_notification/send_user_confirmation.
    """
    normalized = (status_value or "").strip().lower()
    if normalized.startswith("rejected_"):
        return ("user_rejected.html", "user_rejected.txt")
    return ("user_receipt.html", "user_receipt.txt")


def select_manager_templates(status_value: str) -> tuple[str, str]:
    """Selecciona plantillas para el manager.

    Usado por: EmailService.send_rent_notification.
    """
    normalized = (status_value or "").strip().lower()
    if normalized.startswith("rejected_"):
        return ("manager_rejected.html", "manager_rejected.txt")
    return ("manager_confirmation.html", "manager_confirmation.txt")


def build_status_context(status_value: str) -> Dict[str, str]:
    """Arma títulos y mensajes según el estado de la reserva.

    Usado por: build_common_context.
    """
    normalized = (status_value or "").strip().lower()
    rejection_reasons = {
        "rejected_not_received": "Pago no recibido",
        "rejected_invalid_proof": "Evidencia inválida",
        "rejected_amount_low": "Monto incompleto",
        "rejected_amount_high": "Monto excedente",
        "rejected_wrong_destination": "Destino incorrecto",
    }

    if normalized.startswith("rejected_"):
        reason = rejection_reasons.get(normalized)
        user_message = (
            f"Tu pago fue rechazado: {reason.lower()}."
            if reason
            else "Tu pago fue rechazado."
        )
        return {
            "user_status_heading": "Reserva rechazada",
            "user_status_message": user_message,
            "manager_status_heading": "Reserva rechazada",
            "manager_status_message": (
                "Se registró un rechazo de pago. Revisa el detalle y registra el motivo."
            ),
        }

    statuses = {
        "reserved": (
            "Reserva confirmada",
            "Tu reserva ha sido confirmada. Te esperamos.",
            "Reserva confirmada",
            "La reserva fue confirmada para el usuario.",
        ),
        "under_review": (
            "Pago en revisión",
            "¡Gracias! Recibimos tu pago y lo estamos revisando. Te avisaremos en cuanto esté confirmado.",
            "Pago en revisión",
            "El usuario envió un pago; la reserva está en revisión.",
        ),
        "pending_payment": (
            "Pago pendiente",
            "Aún no hemos recibido tu pago. Completa el pago para asegurar tu horario.",
            "Pago pendiente",
            "La reserva sigue pendiente de pago.",
        ),
        "pending_proof": (
            "Falta evidencia de pago",
            "Aún no registramos evidencia de tu pago. Súbela desde la app para continuar.",
            "Falta evidencia de pago",
            "El usuario aún no sube evidencia de pago.",
        ),
        "proof_submitted": (
            "Evidencia recibida",
            "Recibimos tu comprobante. Lo revisaremos y te avisaremos pronto.",
            "Evidencia recibida",
            "El usuario subió evidencia de pago.",
        ),
        "needs_info": (
            "Necesitamos más información",
            "La evidencia no fue suficiente o no coincide. Por favor envía más detalle desde la app.",
            "Se requiere información adicional",
            "La evidencia del usuario es insuficiente o incorrecta.",
        ),
        "cancelled": (
            "Reserva cancelada",
            "Tu reserva fue cancelada.",
            "Reserva cancelada",
            "La reserva fue cancelada.",
        ),
        "fullfilled": (
            "Reserva completada",
            "Tu reserva se realizó con éxito. ¡Gracias por jugar con Cuadra!",
            "Reserva completada",
            "La reserva fue completada.",
        ),
        "expired_no_proof": (
            "Reserva expirada",
            "El plazo venció sin evidencia de pago. Puedes crear una nueva reserva desde la app.",
            "Reserva expirada",
            "La reserva expiró por falta de evidencia.",
        ),
        "expired_slot_unavailable": (
            "Reserva expirada",
            "El horario ya no estaba disponible al validar el pago. Elige otro cupo en la app.",
            "Reserva expirada",
            "El horario dejó de estar disponible.",
        ),
        "dispute_open": (
            "Caso en revisión",
            "Hay un caso abierto con esta reserva. Nuestro equipo lo está revisando.",
            "Caso en revisión",
            "Se abrió un caso para esta reserva.",
        ),
        "dispute_resolved": (
            "Caso resuelto",
            "La disputa fue resuelta.",
            "Caso resuelto",
            "La disputa fue resuelta.",
        ),
    }

    if normalized in statuses:
        user_heading, user_message, manager_heading, manager_message = statuses[normalized]
    else:
        user_heading = "Actualizacion de reserva"
        user_message = "Tu reserva fue actualizada."
        manager_heading = "Actualizacion de reserva"
        manager_message = "La reserva fue actualizada."

    return {
        "user_status_heading": user_heading,
        "user_status_message": user_message,
        "manager_status_heading": manager_heading,
        "manager_status_message": manager_message,
    }


def build_user_subject(status_value: str) -> str:
    """Determina el subject según el estado.

    Usado por: EmailService.send_user_confirmation.
    """
    normalized = (status_value or "").strip().lower()
    if not normalized:
        return settings.USER_CONFIRMATION_SUBJECT

    status_subjects = {
        "reserved": "Cuadra · Reserva confirmada",
        "under_review": "Cuadra · Pago en revisión",
        "pending_payment": "Cuadra · Pago pendiente",
        "pending_proof": "Cuadra · Falta evidencia de pago",
        "proof_submitted": "Cuadra · Evidencia recibida",
        "needs_info": "Cuadra · Necesitamos más información",
        "cancelled": "Cuadra · Reserva cancelada",
        "fullfilled": "Cuadra · Reserva completada",
        "expired_no_proof": "Cuadra · Reserva expirada (sin evidencia)",
        "expired_slot_unavailable": "Cuadra · Reserva expirada (sin disponibilidad)",
        "dispute_open": "Cuadra · Caso en revisión",
        "dispute_resolved": "Cuadra · Caso resuelto",
        "rejected_not_received": "Cuadra · Reserva rechazada (pago no recibido)",
        "rejected_invalid_proof": "Cuadra · Reserva rechazada (evidencia inválida)",
        "rejected_amount_low": "Cuadra · Reserva rechazada (monto incompleto)",
        "rejected_amount_high": "Cuadra · Reserva rechazada (monto excedente)",
        "rejected_wrong_destination": "Cuadra · Reserva rechazada (destino incorrecto)",
    }

    if normalized.startswith("rejected_") and normalized not in status_subjects:
        return "Cuadra · Reserva rechazada"

    return status_subjects.get(normalized, settings.USER_CONFIRMATION_SUBJECT)


def build_manager_subject(status_value: str) -> str:
    """Asunto del correo al administrador del campus según el estado."""
    normalized = (status_value or "").strip().lower()
    if not normalized:
        return settings.MANAGER_CONFIRMATION_SUBJECT

    subjects = {
        "reserved": "Cuadra · Nueva reserva confirmada",
        "under_review": "Cuadra · Pago en revisión",
        "pending_payment": "Cuadra · Reserva con pago pendiente",
        "pending_proof": "Cuadra · Falta evidencia de pago",
        "proof_submitted": "Cuadra · Evidencia de pago recibida",
        "needs_info": "Cuadra · Reserva requiere más información",
        "cancelled": "Cuadra · Reserva cancelada",
        "fullfilled": "Cuadra · Reserva completada",
        "expired_no_proof": "Cuadra · Reserva expirada (sin evidencia)",
        "expired_slot_unavailable": "Cuadra · Reserva expirada (sin cupo)",
        "dispute_open": "Cuadra · Disputa abierta",
        "dispute_resolved": "Cuadra · Disputa resuelta",
        "rejected_not_received": "Cuadra · Reserva rechazada (pago no recibido)",
        "rejected_invalid_proof": "Cuadra · Reserva rechazada (evidencia inválida)",
        "rejected_amount_low": "Cuadra · Reserva rechazada (monto incompleto)",
        "rejected_amount_high": "Cuadra · Reserva rechazada (monto excedente)",
        "rejected_wrong_destination": "Cuadra · Reserva rechazada (destino incorrecto)",
    }
    if normalized.startswith("rejected_") and normalized not in subjects:
        return "Cuadra · Reserva rechazada"
    return subjects.get(normalized, settings.MANAGER_CONFIRMATION_SUBJECT)


__all__ = [
    "select_user_templates",
    "select_manager_templates",
    "build_status_context",
    "build_user_subject",
    "build_manager_subject",
]
