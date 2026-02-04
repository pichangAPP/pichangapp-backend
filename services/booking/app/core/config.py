import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    PROJECT_NAME: str = "Booking Service"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "changeme")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    AUTH_SERVICE_URL: str = os.getenv("AUTH_SERVICE_URL", "http://localhost:8000")
    AUTH_INTERNAL_API_KEY: str = os.getenv("AUTH_INTERNAL_API_KEY", "")
    AUTH_SERVICE_TIMEOUT: float = float(os.getenv("AUTH_SERVICE_TIMEOUT", "10"))


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
