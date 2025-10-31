"""Common dependencies for the payment service."""

from collections.abc import Generator

from app.core.database import SessionLocal


def get_db() -> Generator:
    """Provide a transactional scope around a series of operations."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


__all__ = ["get_db"]
