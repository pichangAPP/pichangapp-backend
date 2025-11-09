"""Database helpers for Rasa custom actions."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional
from urllib.parse import quote_plus, urlencode

from sqlalchemy import Connection, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import InterfaceError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from .config import settings

LOGGER = logging.getLogger(__name__)

_ENGINE: Engine | None = None
_DATABASE_URL: str | None = None
_SESSION_FACTORY: Optional[sessionmaker] = None


class DatabaseError(RuntimeError):
    """Raised when a database interaction cannot be completed."""


def _reset_engine() -> None:
    """Dispose the existing engine and session factory."""

    global _ENGINE, _SESSION_FACTORY
    if _ENGINE is not None:
        _ENGINE.dispose()
    _ENGINE = None
    _SESSION_FACTORY = None


def _compose_query_params() -> Dict[str, str]:
    params: Dict[str, str] = {}

    if settings.POSTGRES_APPLICATION_NAME:
        params["application_name"] = settings.POSTGRES_APPLICATION_NAME
    if settings.POSTGRES_SSL_MODE:
        params["sslmode"] = settings.POSTGRES_SSL_MODE
    if settings.POSTGRES_SSL_ROOT_CERT:
        params["sslrootcert"] = settings.POSTGRES_SSL_ROOT_CERT
    if settings.POSTGRES_SSL_CERT:
        params["sslcert"] = settings.POSTGRES_SSL_CERT
    if settings.POSTGRES_SSL_KEY:
        params["sslkey"] = settings.POSTGRES_SSL_KEY

    return params


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
        user_part = quote_plus(user) if user else ""
        password_part = quote_plus(password) if password else ""
        if user_part and password_part:
            credentials = f"{user_part}:{password_part}"  # pragma: no cover - formatting
        elif user_part:
            credentials = user_part
        else:
            credentials = ""
        authority = f"{host}:{port}" if port else host
        if credentials:
            url = f"postgresql+psycopg2://{credentials}@{authority}/{db_name}"
        else:
            url = f"postgresql+psycopg2://{authority}/{db_name}"

        params = _compose_query_params()
        if params:
            url = f"{url}?{urlencode(params)}"
    elif settings.POSTGRES_SSL_MODE and "sslmode" not in url:
        params = _compose_query_params()
        if params:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{urlencode(params)}"

    _DATABASE_URL = url
    return url


def _base_connect_args() -> Dict[str, Any]:
    args: Dict[str, Any] = {
        "keepalives": 1,
        "keepalives_idle": 60,
        "keepalives_interval": 30,
        "keepalives_count": 5,
    }
    if settings.POSTGRES_SSL_MODE:
        args["sslmode"] = settings.POSTGRES_SSL_MODE
    if settings.POSTGRES_SSL_ROOT_CERT:
        args["sslrootcert"] = settings.POSTGRES_SSL_ROOT_CERT
    if settings.POSTGRES_SSL_CERT:
        args["sslcert"] = settings.POSTGRES_SSL_CERT
    if settings.POSTGRES_SSL_KEY:
        args["sslkey"] = settings.POSTGRES_SSL_KEY
    if settings.POSTGRES_APPLICATION_NAME:
        args["application_name"] = settings.POSTGRES_APPLICATION_NAME
    return args


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
            connect_args=_base_connect_args(),
            future=True,
        )
    return _ENGINE


@contextmanager
def get_connection() -> Iterator[Connection]:
    attempts = 0
    while True:
        engine = get_engine()
        try:
            with engine.begin() as connection:
                yield connection
            break
        except (OperationalError, InterfaceError) as exc:
            attempts += 1
            LOGGER.warning("Database connection failed (attempt %s): %s", attempts, exc)
            if attempts > 2:
                LOGGER.exception("Database error: %s", exc)
                raise DatabaseError(str(exc)) from exc
            _reset_engine()
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

    attempts = 0
    session: Session
    while True:
        session_factory = _get_session_factory()
        try:
            session = session_factory()
            break
        except (OperationalError, InterfaceError) as exc:
            attempts += 1
            LOGGER.warning("Database session factory failed (attempt %s): %s", attempts, exc)
            if attempts > 2:
                raise DatabaseError(str(exc)) from exc
            _reset_engine()
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
