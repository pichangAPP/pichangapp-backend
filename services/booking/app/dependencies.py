from collections.abc import Iterator

from app.core.database import SessionLocal


def get_db() -> Iterator:
    """Yield a SQLAlchemy session and ensure it is closed afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
