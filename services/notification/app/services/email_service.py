"""High level email orchestration for the notification service."""

from __future__ import annotations

import base64
import logging
import re
from uuid import uuid4
from urllib.parse import quote
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

import qrcode
from qrcode import constants
from qrcode.exceptions import DataOverflowError
from PIL import Image, ImageDraw, ImageFont
from firebase_admin import storage

from app.core.config import settings
from app.core.firebase import get_firebase_app
from app.models import EmailAttachment, EmailContent
from app.repository import EmailRepository
from app.schemas import NotificationRequest

logger = logging.getLogger(__name__)


class EmailService:
    """Render templates and deliver emails for reservation notifications."""

    def __init__(
        self,
        *,
        repository: EmailRepository | None = None,
        templates_path: Optional[Path] = None,
    ):
        self._repository = repository or EmailRepository()
        self._templates_path = templates_path or Path(__file__).resolve().parent.parent / "templates"
        self._environment = Environment(
            loader=FileSystemLoader(self._templates_path),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        if value.tzinfo:
            return value.strftime("%d/%m/%Y %H:%M %Z")
        return value.strftime("%d/%m/%Y %H:%M")

    @staticmethod
    def _format_decimal(value: Decimal) -> str:
        return f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")

    def _build_common_context(self, payload: NotificationRequest) -> Dict[str, Any]:
        rent = payload.rent
        campus = rent.campus
        status_context = self._build_status_context(rent.status)
        context: Dict[str, Any] = {
            "rent": rent,
            "user": payload.user,
            "manager": payload.manager,
            "campus": campus,
            "field_name": rent.field_name,
            "date_range": f"{self._format_datetime(rent.start_time)} - {self._format_datetime(rent.end_time)}",
            "start_time_display": self._format_datetime(rent.start_time),
            "end_time_display": self._format_datetime(rent.end_time),
            "payment_deadline_display": self._format_datetime(rent.payment_deadline),
            "amount_display": self._format_decimal(rent.mount),
        }
        context.update(status_context)
        return context

    @staticmethod
    def _select_user_templates(status_value: str) -> tuple[str, str]:
        normalized = (status_value or "").strip().lower()
        if normalized.startswith("rejected_"):
            return ("user_rejected.html", "user_rejected.txt")
        return ("user_receipt.html", "user_receipt.txt")

    @staticmethod
    def _select_manager_templates(status_value: str) -> tuple[str, str]:
        normalized = (status_value or "").strip().lower()
        if normalized.startswith("rejected_"):
            return ("manager_rejected.html", "manager_rejected.txt")
        return ("manager_confirmation.html", "manager_confirmation.txt")

    @staticmethod
    def _build_status_context(status_value: str) -> Dict[str, str]:
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

    @staticmethod
    def _build_user_subject(status_value: str) -> str:
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

    def _render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        try:
            template = self._environment.get_template(template_name)
        except TemplateNotFound as exc:  # pragma: no cover - configuration error
            raise RuntimeError(f"Email template '{template_name}' not found") from exc
        return template.render(**context)

    def _build_email(
        self,
        *,
        subject: str,
        recipient: str,
        html_template: str,
        text_template: str,
        context: Dict[str, Any],
        attachments: Sequence[EmailAttachment] | None = None,
    ) -> EmailContent:
        html_body = self._render_template(html_template, context)
        text_body = self._render_template(text_template, context)
        return EmailContent(
            subject=subject,
            recipients=[recipient],
            html_body=html_body,
            text_body=text_body,
            attachments=tuple(attachments or ()),
        )

    @staticmethod
    def _build_attachment_data_uri(attachment: EmailAttachment) -> str:
        encoded = base64.b64encode(attachment.data).decode("ascii")
        return f"{attachment.content_type};base64,{encoded}"

    @staticmethod
    def _build_qr_attachment(target: str, filename_hint: str) -> EmailAttachment:
        safe_hint = re.sub(r"[^A-Za-z0-9_-]", "_", filename_hint)
        qr = qrcode.QRCode(
            version=None,
            error_correction=constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )

        try:
            qr.add_data(target)
            qr.make(fit=True)
        except (DataOverflowError, ValueError) as exc:  # pragma: no cover - defensive
            logger.error("Error generando el QR %s: %s", safe_hint, exc)
            fallback_qr = qrcode.QRCode(
                version=1,
                error_correction=constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            fallback_qr.add_data("RESERVA PICHANGAPP")
            fallback_qr.make(fit=True)
            qr = fallback_qr

        image = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        filename = f"qr-{safe_hint}.png"
        return EmailAttachment(
            filename=filename,
            content_type="image/png",
            data=buffer.getvalue(),
        )

    def _build_reservation_pass(self, payload: NotificationRequest) -> EmailAttachment:
        rent = payload.rent
        campus = rent.campus
        user = payload.user

        # Generate a lightweight boarding-pass style PNG on the fly so emails
        # always include a scannable, offline-friendly proof of reservation.
        width, height = 900, 640
        background = "#f8fafc"
        accent = "#2563eb"
        text_color = "#0f172a"

        image = Image.new("RGB", (width, height), background)
        draw = ImageDraw.Draw(image)
        header_font = ImageFont.load_default()
        body_font = ImageFont.load_default()

        padding = 40
        draw.rectangle([0, 0, width, 140], fill=accent)
        draw.text((padding, 40), "Pichangapp", fill="#ffffff", font=header_font)
        draw.text(
            (padding, 80),
            f"Comprobante de reserva #{rent.rent_id}",
            fill="#ffffff",
            font=header_font,
        )

        y = 180
        line_spacing = 34

        details = [
            ("Titular", f"{user.name} {user.lastname}"),
            ("Correo", user.email),
            ("Campus", campus.name),
            ("Dirección", f"{campus.address}, {campus.district}"),
            ("Campo", rent.field_name),
            ("Horario", f"{self._format_datetime(rent.start_time)} - {self._format_datetime(rent.end_time)}"),
            ("Periodo", rent.period),
            ("Estado", rent.status.upper()),
            ("Monto pagado", f"S/ {self._format_decimal(rent.mount)}"),
            ("Límite de pago", self._format_datetime(rent.payment_deadline)),
        ]

        for label, value in details:
            draw.text((padding, y), f"{label}:", fill=text_color, font=body_font)
            draw.text((padding + 220, y), value, fill=text_color, font=body_font)
            y += line_spacing

        footer_text = "Presenta esta imagen en recepción para validar tu reserva."
        draw.text((padding, height - 80), footer_text, fill=text_color, font=body_font)

        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return EmailAttachment(
            filename=f"reserva-{rent.rent_id}.png",
            content_type="image/png",
            data=buffer.getvalue(),
        )

    @staticmethod
    def _build_pass_link(payload: NotificationRequest, *, override_url: Optional[str] = None) -> str:
        """Return a concise link or token to recover the reservation pass.

        If ``RESERVATION_PASS_URL_TEMPLATE`` is configured, it can include placeholders
        compatible with ``str.format`` such as ``{rent_id}``, ``{schedule_day}``, and
        ``{user_email}``. When not configured, fall back to an internal token so the QR
        content remains small and still identifies the reservation.
        """

        if override_url:
            return override_url

        template = getattr(settings, "RESERVATION_PASS_URL_TEMPLATE", "")
        if template:
            try:
                return template.format(
                    rent_id=payload.rent.rent_id,
                    schedule_day=payload.rent.schedule_day,
                    user_email=payload.user.email,
                )
            except KeyError as exc:  # pragma: no cover - defensive logging only
                logger.warning(
                    "Plantilla RESERVATION_PASS_URL_TEMPLATE inválida: %s", exc
                )

        # Fallback: compact token with the most relevant identifiers.
        return (
            f"pichangapp:reserva:{payload.rent.rent_id}:{payload.rent.schedule_day}"  # noqa: E501
        )

    def _upload_pass_to_firebase(
        self,
        *,
        attachment: EmailAttachment,
        payload: NotificationRequest,
    ) -> Optional[str]:
        bucket_name = getattr(settings, "FIREBASE_STORAGE_BUCKET", "")
        if not bucket_name:
            return None

        try:
            app = get_firebase_app()
            bucket = storage.bucket(bucket_name, app=app)
            object_name = f"reservas/{payload.rent.rent_id}.png"
            blob = bucket.blob(object_name)
            token = uuid4().hex
            blob.metadata = {"firebaseStorageDownloadTokens": token}
            blob.upload_from_string(attachment.data, content_type=attachment.content_type)
            encoded_name = quote(object_name, safe="")
            return (
                "https://firebasestorage.googleapis.com/v0/b/"
                f"{bucket_name}/o/{encoded_name}?alt=media&token={token}"
            )
        except Exception as exc:  # pragma: no cover - external dependency
            logger.warning("No se pudo subir comprobante a Firebase: %s", exc)
            return None

    def send_rent_notification(self, payload: NotificationRequest) -> None:
        """Send the rent confirmation emails for manager and user."""

        context = self._build_common_context(payload)
        user_html, user_text = self._select_user_templates(payload.rent.status)
        reservation_pass = self._build_reservation_pass(payload)
        firebase_url = self._upload_pass_to_firebase(
            attachment=reservation_pass,
            payload=payload,
        )
        pass_link = self._build_pass_link(payload, override_url=firebase_url)

        user_qr = self._build_qr_attachment(
            pass_link,
            f"reserva-{payload.rent.rent_id}-usuario",
        )
        user_email = self._build_email(
            subject=settings.USER_RECEIPT_SUBJECT,
            recipient=payload.user.email,
            html_template=user_html,
            text_template=user_text,
            context=context,
            attachments=[reservation_pass, user_qr],
        )
        self._repository.send_email(user_email)
        logger.info(
            "Reservation receipt sent to %s for rent %s",
            user_email.primary_recipient(),
            payload.rent.rent_id,
        )

        if payload.manager is None:
            logger.info(
                "No campus manager configured for campus %s; skipping manager email",
                payload.rent.campus.id_campus,
            )
            return

        manager_context = dict(context)
        manager_context["recipient"] = payload.manager
        manager_html, manager_text = self._select_manager_templates(payload.rent.status)

        manager_qr = self._build_qr_attachment(
            pass_link,
            f"reserva-{payload.rent.rent_id}-administrador",
        )
        manager_email = self._build_email(
            subject=settings.MANAGER_CONFIRMATION_SUBJECT,
            recipient=payload.manager.email,
            html_template=manager_html,
            text_template=manager_text,
            context=manager_context,
            attachments=[reservation_pass, manager_qr],
        )
        self._repository.send_email(manager_email)
        logger.info(
            "Reservation confirmation sent to manager %s for rent %s",
            manager_email.primary_recipient(),
            payload.rent.rent_id,
        )

    def send_user_confirmation(self, payload: NotificationRequest) -> None:
        """Send a reservation confirmation email only to the user."""

        context = self._build_common_context(payload)
        user_html, user_text = self._select_user_templates(payload.rent.status)
        reservation_pass = self._build_reservation_pass(payload)
        firebase_url = self._upload_pass_to_firebase(
            attachment=reservation_pass,
            payload=payload,
        )
        pass_link = self._build_pass_link(payload, override_url=firebase_url)

        user_qr = self._build_qr_attachment(
            pass_link,
            f"reserva-{payload.rent.rent_id}-usuario",
        )
        user_email = self._build_email(
            subject=self._build_user_subject(payload.rent.status),
            recipient=payload.user.email,
            html_template=user_html,
            text_template=user_text,
            context=context,
            attachments=[reservation_pass, user_qr],
        )
        self._repository.send_email(user_email)
        logger.info(
            "Reservation confirmation sent to user %s for rent %s",
            user_email.primary_recipient(),
            payload.rent.rent_id,
        )


__all__ = ["EmailService"]
