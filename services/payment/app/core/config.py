"""Configuration management for the payment service."""

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = os.getenv("PAYMENT_PROJECT_NAME", "Payment Service")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    AUTH_SERVICE_URL: str = os.getenv("AUTH_SERVICE_URL", "")
    AUTH_INTERNAL_API_KEY: str = os.getenv("AUTH_INTERNAL_API_KEY", "")
    AUTH_SERVICE_TIMEOUT: int = int(os.getenv("AUTH_SERVICE_TIMEOUT", "10"))
    PAYMENT_ALLOWED_STATUSES: str = os.getenv(
        "PAYMENT_ALLOWED_STATUSES",
        "pending,paid,failed,cancelled",
    )

    @property
    def payment_allowed_statuses(self) -> tuple[str, ...]:
        normalized = [
            status.strip().lower()
            for status in self.PAYMENT_ALLOWED_STATUSES.split(",")
            if status.strip()
        ]
        if not normalized:
            normalized = ["pending", "paid", "failed", "cancelled"]
        return tuple(dict.fromkeys(normalized))


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


__all__ = ["settings", "Settings", "get_settings"]
