"""Configuration settings for the reservation service."""

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = "Auth Service"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = os.getenv("ALGORITHM", "")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    REFRESH_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", "10080"))
    FIREBASE_CREDENTIALS_PATH: str = os.getenv("FIREBASE_CREDENTIALS_PATH", "")
    FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "")
    DEFAULT_SOCIAL_ROLE_ID: int = int(os.getenv("DEFAULT_SOCIAL_ROLE_ID", "1"))
    NOTIFICATION_SERVICE_URL: str = os.getenv(
        "NOTIFICATION_SERVICE_URL",
        "http://localhost:8004",
    )
    NOTIFICATION_SERVICE_TIMEOUT: float = float(
        os.getenv("NOTIFICATION_SERVICE_TIMEOUT", "10")
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
