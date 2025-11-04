"""Database helpers for Rasa custom actions."""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Iterator, Optional

from dotenv import load_dotenv
from sqlalchemy import Connection, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

LOGGER = logging.getLogger(__name__)

_ENGINE: Engine | None = None
_SESSION_FACTORY: Optional[sessionmaker] = None
_DATABASE_URL: Optional[str] = None


class DatabaseError(RuntimeError):
    """Raised when a database interaction cannot be completed."""


def _build_database_url() -> str:
    global _DATABASE_URL
    if _DATABASE_URL:
        return _DATABASE_URL

    url = os.getenv("CHATBOT_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        host = os.getenv("POSTGRES_HOST", "localhost")
        port = os.getenv("POSTGRES_PORT", "")
        user = os.getenv("POSTGRES_USER", "")
        password = os.getenv("POSTGRES_PASSWORD", "")
        db_name = os.getenv("POSTGRES_DB", os.getenv("DB_NAME", ""))
        url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"

    _DATABASE_URL = url
    return url


def get_engine() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        database_url = _build_database_url()
        LOGGER.info("Connecting Rasa actions to %s", database_url)
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


__all__ = ["DatabaseError", "get_connection", "get_engine", "get_session"]
