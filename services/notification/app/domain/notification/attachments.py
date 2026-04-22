"""Generación de adjuntos y recursos para emails de notificación."""
from __future__ import annotations

import base64
import logging
import re
import time
from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.parse import quote
from uuid import uuid4

import qrcode
from jose import JWTError, jwt
from PIL import Image, ImageDraw, ImageFont
from qrcode import constants
from qrcode.exceptions import DataOverflowError
from firebase_admin import storage

from app.core.config import settings
from app.core.firebase import get_firebase_app
from app.domain.notification.branding import get_brand_logo_path
from app.models import EmailAttachment
from app.schemas import NotificationRequest
from app.domain.notification.context import (
    format_date_range,
    format_datetime,
    format_decimal,
    humanize_rent_status,
)

logger = logging.getLogger(__name__)

_PASS_JWT_ALG = "HS256"

_FONT_CANDIDATES = [
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
]


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in _FONT_CANDIDATES:
        if candidate.is_file():
            try:
                return ImageFont.truetype(str(candidate), size)
            except OSError:
                continue
    return ImageFont.load_default()


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
        fallback_qr.add_data("https://cuadra.app")
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


def _qr_pil_image(target: str, *, box_size: int = 7, border: int = 2) -> Image.Image:
    qr = qrcode.QRCode(
        version=None,
        error_correction=constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(target)
    qr.make(fit=True)
    return qr.make_image(fill_color="#0f172a", back_color="white").convert("RGB")


def build_pass_token(payload: NotificationRequest) -> str:
    """JWT firmado: payload bajo clave "p" y expiración, para acortar vida útil del enlace."""
    secret = (settings.RESERVATION_PASS_TOKEN_SECRET or "").strip() or "change-me-reservation-pass-secret"
    days = max(1, int(getattr(settings, "RESERVATION_PASS_TOKEN_EXPIRE_DAYS", 14)))
    exp = int(time.time()) + days * 86400
    body = {"p": payload.model_dump(mode="json"), "exp": exp}
    return jwt.encode(body, secret, algorithm=_PASS_JWT_ALG)


def parse_pass_token(token: str) -> Optional[NotificationRequest]:
    """Valida el JWT y reconstruye el payload."""
    secret = (settings.RESERVATION_PASS_TOKEN_SECRET or "").strip() or "change-me-reservation-pass-secret"
    if not token:
        return None
    try:
        data = jwt.decode(token, secret, algorithms=[_PASS_JWT_ALG])
    except JWTError:
        return None
    inner = data.get("p")
    if inner is not None:
        try:
            return NotificationRequest.model_validate(inner)
        except Exception:  # pragma: no cover
            return None
    try:
        return NotificationRequest.model_validate(data)
    except Exception:  # pragma: no cover - tokens antiguos sin envoltura "p"
        return None


def build_pass_link(payload: NotificationRequest, *, firebase_url: Optional[str] = None) -> str:
    """URL que debe codificar el QR (boleta PNG o enlace directo si hay Firebase)."""
    template = (getattr(settings, "RESERVATION_PASS_URL_TEMPLATE", "") or "").strip()
    token = build_pass_token(payload)
    if template:
        try:
            return template.format(
                rent_id=payload.rent.rent_id,
                schedule_day=payload.rent.schedule_day,
                user_email=payload.user.email,
                token=token,
            )
        except KeyError as exc:  # pragma: no cover - defensive logging only
            logger.warning("Plantilla RESERVATION_PASS_URL_TEMPLATE inválida: %s", exc)

    base = (getattr(settings, "RESERVATION_PASS_FALLBACK_BASE_URL", "") or "").strip().rstrip("/")
    if base:
        return f"{base}?token={quote(token, safe='')}"

    if firebase_url:
        return firebase_url

    return f"cuadra://reserva/{payload.rent.rent_id}"


def build_reservation_pass(payload: NotificationRequest, *, pass_link: str) -> EmailAttachment:
    """Boleta PNG con marca Cuadra!, datos de la reserva y QR a la misma boleta."""
    rent = payload.rent
    campus = rent.campus
    user = payload.user

    width, height = 1080, 1280
    bg = "#f1f5f9"
    accent = "#2563eb"
    text = "#0f172a"
    muted = "#64748b"

    image = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(image)

    title_font = _load_font(42)
    subtitle_font = _load_font(28)
    label_font = _load_font(24)
    value_font = _load_font(24)
    small_font = _load_font(20)

    header_h = 200
    draw.rectangle([0, 0, width, header_h], fill=accent)

    logo_path = get_brand_logo_path()
    if logo_path.is_file():
        try:
            logo = Image.open(logo_path).convert("RGBA")
            max_logo_h = 120
            ratio = max_logo_h / max(logo.height, 1)
            new_w = max(int(logo.width * ratio), 1)
            new_h = max(int(logo.height * ratio), 1)
            logo = logo.resize((new_w, new_h), Image.Resampling.LANCZOS)
            lx = 48
            ly = (header_h - new_h) // 2
            image.paste(logo, (lx, ly), logo)
            text_x = lx + new_w + 32
        except OSError as exc:
            logger.warning("No se pudo cargar el logo de marca: %s", exc)
            text_x = 48
    else:
        text_x = 48

    brand = getattr(settings, "APP_BRAND_NAME", "Cuadra!")
    draw.text((text_x, 48), brand, fill="#ffffff", font=title_font)
    draw.text(
        (text_x, 110),
        f"Boleta digital · Reserva #{rent.rent_id}",
        fill="#e0e7ff",
        font=subtitle_font,
    )

    card_top = header_h + 40
    card_margin = 48
    draw.rounded_rectangle(
        [card_margin, card_top, width - card_margin, height - 220],
        radius=24,
        fill="#ffffff",
        outline="#e2e8f0",
        width=2,
    )

    inner_x = card_margin + 40
    y = card_top + 36
    line_gap = 8

    details: list[tuple[str, str]] = [
        ("Titular", f"{user.name} {user.lastname}".strip()),
        ("Correo", user.email),
        ("Campus", campus.name),
        ("Dirección", f"{campus.address}, {campus.district}"),
        ("Campo", rent.field_name),
        (
            "Horario",
            format_date_range(
                rent.start_time,
                rent.end_time,
                schedule_day=rent.schedule_day,
            ),
        ),
        ("Periodo", rent.period),
        ("Estado", humanize_rent_status(rent.status)),
        ("Monto", f"S/ {format_decimal(rent.mount)}"),
        ("Límite de pago", format_datetime(rent.payment_deadline)),
    ]

    label_w = 280
    value_max_w = width - inner_x * 2 - label_w - 24
    line_h = _line_height(value_font)

    for label, value in details:
        draw.text((inner_x, y), f"{label}", fill=muted, font=label_font)
        wrapped = _wrap_text(value, value_font, value_max_w)
        vy = y
        for line in wrapped:
            draw.text((inner_x + label_w, vy), line, fill=text, font=value_font)
            vy += line_h + line_gap
        y = vy + 18

    qr_img = _qr_pil_image(pass_link, box_size=6, border=2)
    qr_size = 240
    qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
    qx = width - card_margin - qr_size - 40
    qy = height - 200
    image.paste(qr_img, (qx, qy))

    draw.text(
        (inner_x, qy + 20),
        "Escanea el código para abrir esta boleta en tu teléfono.",
        fill=text,
        font=small_font,
    )
    draw.text(
        (inner_x, qy + 56),
        "Muéstrala en recepción para validar tu reserva.",
        fill=muted,
        font=small_font,
    )

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return EmailAttachment(
        filename=f"boleta-cuadra-{rent.rent_id}.png",
        content_type="image/png",
        data=buffer.getvalue(),
    )


def _line_height(font: ImageFont.ImageFont) -> int:
    if hasattr(font, "size"):
        return int(font.size * 1.2)
    return 24


def _text_width(font: ImageFont.ImageFont, text: str) -> float:
    if hasattr(font, "getlength"):
        return float(font.getlength(text))
    if hasattr(font, "getbbox"):
        bbox = font.getbbox(text)
        return float(bbox[2] - bbox[0])
    return float(font.getsize(text)[0])


def _wrap_text(text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    if max_width <= 0:
        return [text]
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for w in words[1:]:
        trial = f"{current} {w}"
        if _text_width(font, trial) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = w
    lines.append(current)
    return lines


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
    "build_pass_token",
    "parse_pass_token",
    "upload_pass_to_firebase",
]
