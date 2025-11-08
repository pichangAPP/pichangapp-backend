"""Shared dependencies for the analytics service."""

from typing import Generator

from app.core.database import SessionLocal


def get_db() -> Generator:
    """Provide a database session for request handling."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


__all__ = ["get_db"]
