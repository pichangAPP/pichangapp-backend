"""Configuration for the notification service."""

import os
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _to_bool(value: str, *, default: bool = False) -> bool:
    lowered = value.strip().lower()
    if not lowered:
        return default
    return lowered in {"true", "1", "yes", "y", "on"}


def _public_api_base() -> str:
    return (os.getenv("PUBLIC_API_BASE_URL") or "").strip().rstrip("/")


def _reservation_pass_fallback_url() -> str:
    direct = (os.getenv("RESERVATION_PASS_FALLBACK_BASE_URL") or "").strip()
    if direct:
        return direct
    base = _public_api_base()
    if base:
        return f"{base}/api/pichangapp/v1/notification/notifications/reservation-pass"
    return ""


class Settings:
    PROJECT_NAME: str = os.getenv("NOTIFICATION_PROJECT_NAME", "Cuadra! Notifications")
    APP_BRAND_NAME: str = os.getenv("APP_BRAND_NAME", "Cuadra!")
    # Logo en cabeceras HTML de correo (URL pública HTTPS; no adjuntar PNG inline).
    EMAIL_BRAND_LOGO_URL: str = (
        os.getenv("EMAIL_BRAND_LOGO_URL", "").strip()
        or "https://cuadraipe.com/images/pichangapp-icon.png"
    )

    # Misma base que auth (schema auth.user_devices).
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    # JWT (mismos valores que el servicio auth).
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")

    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: Optional[str] = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "Cuadra!")
    SMTP_USE_TLS: bool = _to_bool(os.getenv("SMTP_USE_TLS", "true"), default=True)
    SMTP_USE_SSL: bool = _to_bool(os.getenv("SMTP_USE_SSL", "false"), default=False)
    SMTP_TIMEOUT: float = float(os.getenv("SMTP_TIMEOUT", "10"))

    MANAGER_CONFIRMATION_SUBJECT: str = os.getenv(
        "MANAGER_CONFIRMATION_SUBJECT",
        "Nueva reserva confirmada",
    )
    USER_RECEIPT_SUBJECT: str = os.getenv(
        "USER_RECEIPT_SUBJECT",
        "Comprobante de tu reserva",
    )

    FIREBASE_CREDENTIALS_PATH: str = os.getenv("FIREBASE_CREDENTIALS_PATH", "")
    FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "")
    FIREBASE_STORAGE_BUCKET: str = os.getenv("FIREBASE_STORAGE_BUCKET", "")
    FCM_FIREBASE_CREDENTIALS_PATH: str = os.getenv(
        "FCM_FIREBASE_CREDENTIALS_PATH", ""
    ).strip()
    FCM_FIREBASE_PROJECT_ID: str = os.getenv("FCM_FIREBASE_PROJECT_ID", "").strip()
    # Opcional: alinear con el canal creado en la app Android (React Native).
    FCM_ANDROID_NOTIFICATION_CHANNEL_ID: str = os.getenv(
        "FCM_ANDROID_NOTIFICATION_CHANNEL_ID", "cuadra_notifications"
    ).strip()
    USER_CONFIRMATION_SUBJECT: str = os.getenv(
        "USER_CONFIRMATION_SUBJECT",
        "Cuadra · Actualización de tu reserva",
    )

    # Plantilla opcional del enlace del QR. Placeholders: {rent_id}, {schedule_day},
    # {user_email}, {token}. Si está vacía, se usa RESERVATION_PASS_FALLBACK_BASE_URL?token=...
    RESERVATION_PASS_URL_TEMPLATE: str = os.getenv("RESERVATION_PASS_URL_TEMPLATE", "")
    PUBLIC_API_BASE_URL: str = _public_api_base()
    RESERVATION_PASS_FALLBACK_BASE_URL: str = _reservation_pass_fallback_url()
    RESERVATION_PASS_TOKEN_SECRET: str = (
        os.getenv("RESERVATION_PASS_TOKEN_SECRET", "") or "change-me-reservation-pass-secret"
    ).strip()
    RESERVATION_PASS_TOKEN_EXPIRE_DAYS: int = int(
        os.getenv("RESERVATION_PASS_TOKEN_EXPIRE_DAYS", "14"),
    )
    # Máximo de respuestas PNG por IP y minuto (GET reservation-pass).
    RESERVATION_PASS_RATE_LIMIT_PER_MINUTE: int = int(
        os.getenv("RESERVATION_PASS_RATE_LIMIT_PER_MINUTE", "40"),
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

__all__ = ["settings", "get_settings", "Settings"]
