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


class Settings:
    PROJECT_NAME: str = os.getenv("NOTIFICATION_PROJECT_NAME", "Notification Service")

    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: Optional[str] = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "Pichangapp Notifications")
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

    # Optional template to build a public URL for the reservation pass. Supports
    # str.format placeholders such as {rent_id}, {schedule_day}, and
    # {user_email}. When empty, the QR will fall back to a compact token.
    RESERVATION_PASS_URL_TEMPLATE: str = os.getenv("RESERVATION_PASS_URL_TEMPLATE", "")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

__all__ = ["settings", "get_settings", "Settings"]
