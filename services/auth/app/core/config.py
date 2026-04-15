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
    # Firebase Admin (verify_id_token / Google Auth): proyecto FCM/Auth, no el de Storage.
    FCM_FIREBASE_CREDENTIALS_PATH: str = (os.getenv("FCM_FIREBASE_CREDENTIALS_PATH") or "").strip()
    FCM_FIREBASE_PROJECT_ID: str = (os.getenv("FCM_FIREBASE_PROJECT_ID") or "").strip()
    DEFAULT_SOCIAL_ROLE_ID: int = int(os.getenv("DEFAULT_SOCIAL_ROLE_ID", "1"))
    AUTH_INTERNAL_API_KEY: str = os.getenv("AUTH_INTERNAL_API_KEY", "")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
