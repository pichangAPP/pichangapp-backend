import logging

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,            # Máx. conexiones en el pool
    max_overflow=20,         # Conexiones extra si el pool está lleno
    pool_timeout=30,         # Espera máx. para obtener una conexión
    pool_recycle=1800,       # Recicla conexiones cada 30 min (evita timeouts del servidor)
    pool_pre_ping=True       # Testea conexión antes de usarla (evita "server closed connection")
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

logger = logging.getLogger(__name__)


def ensure_booking_functions() -> None:
    function_sql = """
    DROP FUNCTION IF EXISTS booking.sync_operating_statuses(text, text, text);

    CREATE OR REPLACE FUNCTION booking.sync_operating_statuses(
      p_tz text DEFAULT 'America/Lima',
      p_status_open text DEFAULT 'active',
      p_status_closed text DEFAULT 'out_of_hours'
    )
    RETURNS void
    LANGUAGE plpgsql
    AS $$
    DECLARE
      v_now_local time;
    BEGIN
      v_now_local := (now() AT TIME ZONE p_tz)::time;

      WITH target AS (
        SELECT
          c.id_campus,
          CASE
            WHEN v_now_local >= c.opentime AND v_now_local < c.closetime
              THEN p_status_open
            ELSE p_status_closed
          END AS target_status
        FROM booking.campus c
        WHERE lower(c.status) NOT IN ('inactive', 'blocked', 'maintenance', 'deleted')
      )
      UPDATE booking.campus c
      SET status = t.target_status,
          updated_at = now()
      FROM target t
      WHERE c.id_campus = t.id_campus
        AND lower(c.status) <> lower(t.target_status);

      WITH target AS (
        SELECT
          f.id_field,
          CASE
            WHEN lower(f.status) = 'occupied' THEN f.status
            WHEN v_now_local >= f.open_time AND v_now_local < f.close_time
             AND v_now_local >= c.opentime AND v_now_local < c.closetime
              THEN p_status_open
            ELSE p_status_closed
          END AS target_status
        FROM booking.field f
        JOIN booking.campus c ON c.id_campus = f.id_campus
        WHERE lower(f.status) NOT IN ('inactive', 'blocked', 'maintenance', 'deleted')
      )
      UPDATE booking.field f
      SET status = t.target_status,
          updated_at = now()
      FROM target t
      WHERE f.id_field = t.id_field
        AND lower(f.status) <> lower(t.target_status);

      WITH target AS (
        SELECT
          b.id_business,
          CASE
            WHEN EXISTS (
              SELECT 1
              FROM booking.campus c
              WHERE c.id_business = b.id_business
                AND lower(c.status) = lower(p_status_open)
            ) THEN p_status_open
            ELSE p_status_closed
          END AS target_status
        FROM booking.business b
        WHERE lower(b.status) NOT IN ('inactive', 'blocked', 'maintenance', 'deleted')
      )
      UPDATE booking.business b
      SET status = t.target_status,
          updated_at = now()
      FROM target t
      WHERE b.id_business = t.id_business
        AND lower(b.status) <> lower(t.target_status);
    END;
    $$;
    """
    try:
        with engine.begin() as connection:
            connection.execute(text(function_sql))
    except SQLAlchemyError as exc:
        logger.exception("Failed to ensure booking stored procedures")
        raise RuntimeError("Failed to initialize booking stored procedures") from exc
