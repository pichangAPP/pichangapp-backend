"""High level email orchestration for the notification service."""

from __future__ import annotations

import base64
import logging
import re
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

from app.core.config import settings
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
        return context

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
    def _build_pass_link(payload: NotificationRequest) -> str:
        """Return a concise link or token to recover the reservation pass.

        If ``RESERVATION_PASS_URL_TEMPLATE`` is configured, it can include placeholders
        compatible with ``str.format`` such as ``{rent_id}``, ``{schedule_day}``, and
        ``{user_email}``. When not configured, fall back to an internal token so the QR
        content remains small and still identifies the reservation.
        """

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

    def send_rent_notification(self, payload: NotificationRequest) -> None:
        """Send the rent confirmation emails for manager and user."""

        context = self._build_common_context(payload)
        reservation_pass = self._build_reservation_pass(payload)
        pass_link = self._build_pass_link(payload)

        user_qr = self._build_qr_attachment(
            pass_link,
            f"reserva-{payload.rent.rent_id}-usuario",
        )
        user_email = self._build_email(
            subject=settings.USER_RECEIPT_SUBJECT,
            recipient=payload.user.email,
            html_template="user_receipt.html",
            text_template="user_receipt.txt",
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

        manager_qr = self._build_qr_attachment(
            pass_link,
            f"reserva-{payload.rent.rent_id}-administrador",
        )
        manager_email = self._build_email(
            subject=settings.MANAGER_CONFIRMATION_SUBJECT,
            recipient=payload.manager.email,
            html_template="manager_confirmation.html",
            text_template="manager_confirmation.txt",
            context=manager_context,
            attachments=[reservation_pass, manager_qr],
        )
        self._repository.send_email(manager_email)
        logger.info(
            "Reservation confirmation sent to manager %s for rent %s",
            manager_email.primary_recipient(),
            payload.rent.rent_id,
        )


__all__ = ["EmailService"]
