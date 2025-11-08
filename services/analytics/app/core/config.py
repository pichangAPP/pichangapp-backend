"""Settings for the analytics service."""

from functools import lru_cache
import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "Analytics Service")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "changeme")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

__all__ = ["settings", "Settings", "get_settings"]
