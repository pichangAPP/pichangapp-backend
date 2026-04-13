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
    TIMEZONE: str = os.getenv("TIMEZONE", "America/Lima")
    # Hostnames permitidos en image_url (coma). Vacío = Firebase Storage por defecto.
    IMAGE_URL_ALLOWED_HOSTS: str = os.getenv("IMAGE_URL_ALLOWED_HOSTS", "")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
