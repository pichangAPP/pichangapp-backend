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
            "Pago en revision",
            "Hemos recibido tu pago. Estamos revisandolo y te avisaremos.",
            "Pago en revision",
            "Se recibio un pago y esta en revision.",
        ),
        "pending_payment": (
            "Pago pendiente",
            "Aun no hemos recibido tu pago.",
            "Pago pendiente",
            "La reserva sigue pendiente de pago.",
        ),
        "pending_proof": (
            "Falta evidencia de pago",
            "Aun no se ha subido evidencia de pago.",
            "Falta evidencia de pago",
            "El usuario aun no sube evidencia de pago.",
        ),
        "proof_submitted": (
            "Evidencia recibida",
            "Hemos recibido tu evidencia. La validaremos pronto.",
            "Evidencia recibida",
            "El usuario subio evidencia de pago.",
        ),
        "needs_info": (
            "Se requiere informacion adicional",
            "La evidencia es insuficiente o incorrecta. Por favor envia mas informacion.",
            "Se requiere informacion adicional",
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
            "Tu reserva se realizo con exito.",
            "Reserva completada",
            "La reserva fue completada.",
        ),
        "expired_no_proof": (
            "Reserva expirada",
            "El plazo vencio sin que se suba evidencia de pago.",
            "Reserva expirada",
            "La reserva expiro por falta de evidencia.",
        ),
        "expired_slot_unavailable": (
            "Reserva expirada",
            "El horario ya no estaba disponible al validar el pago.",
            "Reserva expirada",
            "El horario dejo de estar disponible.",
        ),
        "dispute_open": (
            "Caso en revision",
            "Se abrio un caso y esta en revision.",
            "Caso en revision",
            "Se abrio un caso para esta reserva.",
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
        "reserved": "Reserva confirmada",
        "under_review": "Pago en revision",
        "pending_payment": "Pago pendiente",
        "pending_proof": "Falta evidencia de pago",
        "proof_submitted": "Evidencia recibida",
        "needs_info": "Se requiere informacion adicional",
        "cancelled": "Reserva cancelada",
        "fullfilled": "Reserva completada",
        "expired_no_proof": "Reserva expirada (sin evidencia)",
        "expired_slot_unavailable": "Reserva expirada (sin disponibilidad)",
        "dispute_open": "Caso en revision",
        "dispute_resolved": "Caso resuelto",
        "rejected_not_received": "Reserva rechazada (pago no recibido)",
        "rejected_invalid_proof": "Reserva rechazada (evidencia invalida)",
        "rejected_amount_low": "Reserva rechazada (monto incompleto)",
        "rejected_amount_high": "Reserva rechazada (monto excedente)",
        "rejected_wrong_destination": "Reserva rechazada (destino incorrecto)",
    }

    if normalized.startswith("rejected_") and normalized not in status_subjects:
        return "Reserva rechazada"

    return status_subjects.get(normalized, settings.USER_CONFIRMATION_SUBJECT)


__all__ = [
    "select_user_templates",
    "select_manager_templates",
    "build_status_context",
    "build_user_subject",
]
