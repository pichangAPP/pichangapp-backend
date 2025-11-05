"""Database helpers shared between the chatbot API and Rasa actions."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import Connection, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

LOGGER = logging.getLogger(__name__)

_ENGINE: Engine | None = None
_DATABASE_URL: str | None = None
_SESSION_FACTORY: sessionmaker | None = None


class DatabaseError(RuntimeError):
    """Raised when the API cannot complete a database operation."""


def _build_database_url() -> str:
    global _DATABASE_URL
    if _DATABASE_URL:
        return _DATABASE_URL

    url = settings.CHATBOT_DATABASE_URL or settings.DATABASE_URL
    if not url:
        host = settings.POSTGRES_HOST
        port = settings.POSTGRES_PORT
        user = settings.POSTGRES_USER
        password = settings.POSTGRES_PASSWORD
        db_name = settings.POSTGRES_DB
        url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"

    _DATABASE_URL = url
    return url


def get_engine() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        database_url = _build_database_url()
        LOGGER.info("Connecting chatbot API to %s", database_url)
        _ENGINE = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=3,
            max_overflow=2,
            pool_recycle=1800,
            pool_timeout=30,
            connect_args={
                "keepalives": 1,
                "keepalives_idle": 60,
                "keepalives_interval": 30,
                "keepalives_count": 5,
            },
            future=True,
        )
    return _ENGINE


@contextmanager
def get_connection() -> Iterator[Connection]:
    engine = get_engine()
    try:
        with engine.begin() as connection:
            yield connection
    except SQLAlchemyError as exc:  # pragma: no cover - defensive
        LOGGER.exception("Database error: %s", exc)
        raise DatabaseError(str(exc)) from exc


def _get_session_factory() -> sessionmaker:
    global _SESSION_FACTORY
    if _SESSION_FACTORY is None:
        engine = get_engine()
        _SESSION_FACTORY = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
    return _SESSION_FACTORY


@contextmanager
def get_session() -> Iterator[Session]:
    """Provide a transactional scope for ORM interactions."""

    session_factory = _get_session_factory()
    session: Session = session_factory()
    try:
        yield session
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        LOGGER.exception("Database session error: %s", exc)
        raise DatabaseError(str(exc)) from exc
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def fetch_user_role(user_id: int) -> Optional[int]:
    """Return the role identifier stored for the given user."""

    with get_connection() as connection:
        result = connection.execute(
            text("SELECT id_role FROM auth.users WHERE id_user = :user_id"),
            {"user_id": user_id},
        )
        value = result.scalar_one_or_none()
        return int(value) if value is not None else None


__all__ = [
    "DatabaseError",
    "fetch_user_role",
    "get_connection",
    "get_engine",
    "get_session",
]
