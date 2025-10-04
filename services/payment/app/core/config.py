"""Application configuration for the payment service."""

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    PROJECT_NAME: str = "Payment Service"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "changeme")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")


@lru_cache()
def get_settings() -> "Settings":
    """Return cached application settings."""

    return Settings()


settings = get_settings()
