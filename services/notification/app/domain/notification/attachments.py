"""Generación de adjuntos y recursos para emails de notificación."""
from __future__ import annotations

import base64
import logging
import re
from io import BytesIO
from typing import Optional
from urllib.parse import quote
from uuid import uuid4

import qrcode
from qrcode import constants
from qrcode.exceptions import DataOverflowError
from PIL import Image, ImageDraw, ImageFont
from firebase_admin import storage

from app.core.config import settings
from app.core.firebase import get_firebase_app
from app.models import EmailAttachment
from app.schemas import NotificationRequest
from app.domain.notification.context import format_datetime, format_decimal

logger = logging.getLogger(__name__)


def build_attachment_data_uri(attachment: EmailAttachment) -> str:
    """Convierte un adjunto a data URI.

    Usado por: escenarios donde se embebe el adjunto en HTML (si aplica).
    """
    encoded = base64.b64encode(attachment.data).decode("ascii")
    return f"{attachment.content_type};base64,{encoded}"


def build_qr_attachment(target: str, filename_hint: str) -> EmailAttachment:
    """Genera un QR como adjunto PNG.

    Usado por: EmailService al enviar confirmaciones.
    """
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


def build_reservation_pass(payload: NotificationRequest) -> EmailAttachment:
    """Crea un comprobante PNG para la reserva.

    Usado por: EmailService en notificaciones.
    """
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
        ("Horario", f"{format_datetime(rent.start_time)} - {format_datetime(rent.end_time)}"),
        ("Periodo", rent.period),
        ("Estado", rent.status.upper()),
        ("Monto pagado", f"S/ {format_decimal(rent.mount)}"),
        ("Límite de pago", format_datetime(rent.payment_deadline)),
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


def build_pass_link(payload: NotificationRequest, *, override_url: Optional[str] = None) -> str:
    """Retorna un link compacto para el comprobante.

    Usado por: EmailService para QR y enlaces.
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
            logger.warning("Plantilla RESERVATION_PASS_URL_TEMPLATE inválida: %s", exc)

    return f"pichangapp:reserva:{payload.rent.rent_id}:{payload.rent.schedule_day}"


def upload_pass_to_firebase(
    *,
    attachment: EmailAttachment,
    payload: NotificationRequest,
) -> Optional[str]:
    """Sube el comprobante a Firebase y retorna la URL pública.

    Usado por: EmailService antes de generar QR.
    """
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


__all__ = [
    "build_attachment_data_uri",
    "build_qr_attachment",
    "build_reservation_pass",
    "build_pass_link",
    "upload_pass_to_firebase",
]
