"""Shared dependencies for the reservation service."""

from typing import Generator

from app.core.database import SessionLocal


def get_db() -> Generator:
    """Provide a transactional scope around a series of operations."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
