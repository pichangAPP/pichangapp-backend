"""Database configuration for the payment service."""

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def verify_database_connection() -> None:
    """Ensure the service can connect to the configured database."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.exception("Database connection validation failed")
        raise RuntimeError("Failed to connect to the payment database") from exc


def ensure_payment_schema() -> None:
    """Create the payment schema if it does not exist."""
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE SCHEMA IF NOT EXISTS payment"))
    except SQLAlchemyError as exc:
        logger.exception("Failed to ensure payment schema exists")
        raise RuntimeError("Failed to initialize payment schema") from exc


__all__ = [
    "engine",
    "SessionLocal",
    "Base",
    "ensure_payment_schema",
    "verify_database_connection",
]
