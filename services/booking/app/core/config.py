import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    PROJECT_NAME: str = "Booking Service"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
