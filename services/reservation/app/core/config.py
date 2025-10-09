"""Configuration settings for the reservation service."""

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application configuration loaded from environment variables."""

    PROJECT_NAME: str = "Reservation Service"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")


@lru_cache()
def get_settings() -> Settings:
    """Return a cached instance of the application settings."""

    return Settings()


settings = get_settings()
