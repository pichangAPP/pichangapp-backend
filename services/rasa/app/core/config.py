"""Configuration helpers for the Rasa service wrapper."""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = "Chatbot Service"
    RASA_SERVER_URL: str = os.getenv("RASA_SERVER_URL", "http://localhost:5005")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    CHATBOT_DATABASE_URL: str | None = os.getenv("CHATBOT_DATABASE_URL")
    DATABASE_URL: str | None = os.getenv("DATABASE_URL")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
    RASA_DEFAULT_SOURCE_MODEL: str = (
        os.getenv("RASA_SOURCE_MODEL")
        or os.getenv("RASA_MODEL_NAME")
        or "rasa-pro"
    )
    REQUEST_TIMEOUT: float = float(os.getenv("CHATBOT_REQUEST_TIMEOUT", "60"))


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
