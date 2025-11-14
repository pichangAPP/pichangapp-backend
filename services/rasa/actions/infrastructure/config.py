"""Configuration helpers for the Rasa actions service."""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    CHATBOT_DATABASE_URL: str | None = os.getenv("CHATBOT_DATABASE_URL")
    DATABASE_URL: str | None = os.getenv("DATABASE_URL")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
    POSTGRES_SSL_MODE: str | None = os.getenv("POSTGRES_SSL_MODE")
    POSTGRES_SSL_ROOT_CERT: str | None = os.getenv("POSTGRES_SSL_ROOT_CERT")
    POSTGRES_SSL_CERT: str | None = os.getenv("POSTGRES_SSL_CERT")
    POSTGRES_SSL_KEY: str | None = os.getenv("POSTGRES_SSL_KEY")
    POSTGRES_APPLICATION_NAME: str | None = os.getenv("POSTGRES_APPLICATION_NAME")
    ANALYTICS_SERVICE_URL: str = os.getenv("ANALYTICS_SERVICE_URL", "http://localhost:8005/api/pichangapp/v1")


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()


settings = get_settings()

__all__ = ["settings", "get_settings", "Settings"]
