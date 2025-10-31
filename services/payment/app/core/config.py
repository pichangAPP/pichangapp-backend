"""Configuration management for the payment service."""

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = os.getenv("PAYMENT_PROJECT_NAME", "Payment Service")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


__all__ = ["settings", "Settings", "get_settings"]
