"""Idempotent DDL for features not managed by Alembic in this repo."""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import engine

logger = logging.getLogger(__name__)


def ensure_field_combination_tables() -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS booking.field_combination (
        id_combination BIGSERIAL PRIMARY KEY,
        id_campus BIGINT NOT NULL
            REFERENCES booking.campus (id_campus) ON DELETE CASCADE,
        name VARCHAR(200) NOT NULL,
        description TEXT,
        status VARCHAR(50) NOT NULL DEFAULT 'active',
        price_per_hour NUMERIC(10, 2) NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ
    );

    CREATE TABLE IF NOT EXISTS booking.field_combination_member (
        id_combination BIGINT NOT NULL
            REFERENCES booking.field_combination (id_combination) ON DELETE CASCADE,
        id_field BIGINT NOT NULL
            REFERENCES booking.field (id_field) ON DELETE CASCADE,
        sort_order INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (id_combination, id_field)
    );

    CREATE INDEX IF NOT EXISTS ix_field_combination_member_field
        ON booking.field_combination_member (id_field);
    """
    try:
        with engine.begin() as conn:
            conn.execute(text(ddl))
    except SQLAlchemyError as exc:
        logger.exception("Failed to ensure field combination tables")
        raise RuntimeError("Failed to initialize field combination tables") from exc


__all__ = ["ensure_field_combination_tables"]
