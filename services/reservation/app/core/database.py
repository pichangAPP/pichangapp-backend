import logging

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

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

logger = logging.getLogger(__name__)


def ensure_rent_schedule_schema() -> None:
    """Create rent_schedule M:N, relax rent.id_schedule nullability, backfill links."""
    ddl = """
    CREATE TABLE IF NOT EXISTS reservation.rent_schedule (
        id_rent BIGINT NOT NULL
            REFERENCES reservation.rent (id_rent) ON DELETE CASCADE,
        id_schedule BIGINT NOT NULL
            REFERENCES reservation.schedule (id_schedule) ON DELETE CASCADE,
        is_primary BOOLEAN NOT NULL DEFAULT false,
        PRIMARY KEY (id_rent, id_schedule)
    );

    CREATE INDEX IF NOT EXISTS ix_rent_schedule_schedule
        ON reservation.rent_schedule (id_schedule);
    """
    try:
        with engine.begin() as connection:
            connection.execute(text(ddl))
            connection.execute(
                text("ALTER TABLE reservation.rent ALTER COLUMN id_schedule DROP NOT NULL;")
            )
            connection.execute(
                text(
                    """
                    INSERT INTO reservation.rent_schedule (id_rent, id_schedule, is_primary)
                    SELECT r.id_rent, r.id_schedule, true
                    FROM reservation.rent r
                    WHERE r.id_schedule IS NOT NULL
                    ON CONFLICT DO NOTHING;
                    """
                )
            )
    except SQLAlchemyError as exc:
        logger.exception("Failed to ensure rent_schedule schema")
        raise RuntimeError("Failed to initialize rent_schedule schema") from exc


def ensure_reservation_functions() -> None:
    function_sql = """
    DROP FUNCTION IF EXISTS reservation.get_rents_by_campus(bigint, text);
    DROP FUNCTION IF EXISTS reservation.cleanup_expired_schedules_safe();
    DROP FUNCTION IF EXISTS reservation.mark_fullfilled_rents();
    DROP FUNCTION IF EXISTS reservation.expire_under_review_after_start();

    CREATE OR REPLACE FUNCTION reservation.get_rents_by_campus(
        p_campus_id bigint,
        p_status text DEFAULT NULL
    )
    RETURNS TABLE (
        id_rent bigint,
        period varchar,
        start_time timestamptz,
        end_time timestamptz,
        initialized timestamptz,
        finished timestamptz,
        status varchar,
        rent_id_status bigint,
        minutes numeric,
        mount numeric,
        date_log timestamptz,
        date_create timestamptz,
        payment_deadline timestamptz,
        capacity integer,
        id_payment bigint,
        payment_code varchar,
        payment_proof_url text,
        payment_reviewed_at timestamptz,
        payment_reviewed_by bigint,
        customer_full_name varchar,
        customer_phone varchar,
        customer_email varchar,
        customer_document varchar,
        customer_notes text,
        id_schedule bigint,
        schedule_day_of_week varchar,
        schedule_start_time timestamptz,
        schedule_end_time timestamptz,
        schedule_status varchar,
        schedule_id_status bigint,
        schedule_price numeric,
        field_id_field bigint,
        field_name varchar,
        field_capacity integer,
        field_surface varchar,
        field_measurement text,
        field_price_per_hour numeric,
        field_status varchar,
        field_open_time time,
        field_close_time time,
        field_minutes_wait numeric,
        field_id_sport integer,
        field_id_campus bigint,
        user_id_user bigint,
        user_name varchar,
        user_lastname varchar,
        user_email varchar,
        user_phone varchar,
        user_imageurl text,
        user_status varchar,
        rent_schedule_is_primary boolean
    )
    LANGUAGE plpgsql
    STABLE
    AS $$
    BEGIN
        RETURN QUERY
        SELECT r.id_rent,
               r.period,
               r.start_time,
               r.end_time,
               r.initialized,
               r.finished,
               r.status,
               r.id_status,
               r.minutes,
               r.mount,
               r.date_log,
               r.date_create,
               r.payment_deadline,
               r.capacity,
               r.id_payment,
               r.payment_code,
               r.payment_proof_url,
               r.payment_reviewed_at,
               r.payment_reviewed_by,
               r.customer_full_name,
               r.customer_phone,
               r.customer_email,
               r.customer_document,
               r.customer_notes,
               r.id_schedule,
               s.day_of_week,
               s.start_time,
               s.end_time,
               s.status,
               s.id_status,
               s.price,
               f.id_field,
               f.field_name,
               f.capacity,
               f.surface,
               f.measurement,
               f.price_per_hour,
               f.status,
               f.open_time,
               f.close_time,
               f.minutes_wait,
               f.id_sport,
               f.id_campus,
               u.id_user,
               u.name,
               u.lastname,
               u.email,
               u.phone,
               u.imageurl,
               u.status,
               COALESCE(rs.is_primary, true) AS rent_schedule_is_primary
        FROM reservation.rent r
        JOIN reservation.rent_schedule rs ON rs.id_rent = r.id_rent
        JOIN reservation.schedule s ON s.id_schedule = rs.id_schedule
        JOIN booking.field f ON f.id_field = s.id_field
        LEFT JOIN auth.users u ON u.id_user = s.id_user
        WHERE f.id_campus = p_campus_id
          AND (p_status IS NULL OR r.status = p_status)
        ORDER BY r.date_create DESC, rs.is_primary DESC, s.id_schedule;
    END;
    $$;

    CREATE OR REPLACE FUNCTION reservation.cleanup_expired_schedules_safe()
    RETURNS void
    LANGUAGE plpgsql
    AS $$
    DECLARE
        v_id_cancelled bigint;
        v_id_available bigint;
    BEGIN
        SELECT MAX(CASE WHEN lower(code) = 'cancelled' THEN id_status END)
          INTO v_id_cancelled
          FROM reservation.status_catalog
         WHERE is_active = true;

        SELECT MAX(CASE WHEN lower(code) = 'available' THEN id_status END)
          INTO v_id_available
          FROM reservation.status_catalog
         WHERE is_active = true;

        -- 1) Cancel expired rents in payment-hold lifecycle.
        UPDATE reservation.rent r
           SET status = 'cancelled',
               id_status = v_id_cancelled
         WHERE r.payment_deadline IS NOT NULL
           AND r.payment_deadline < now()
           AND v_id_cancelled IS NOT NULL
           AND lower(r.status) IN (
               'pending_payment',
               'pending_proof',
               'needs_info',
               'pending',
               'hold_payment'
           );

        -- 2) Release schedules with no active rents (multi-field aware via rent_schedule).
        WITH schedule_rent_map AS (
            SELECT DISTINCT rs.id_schedule, rs.id_rent
              FROM reservation.rent_schedule rs
            UNION
            SELECT DISTINCT r.id_schedule, r.id_rent
              FROM reservation.rent r
             WHERE r.id_schedule IS NOT NULL
        )
        UPDATE reservation.schedule s
           SET status = 'available',
               id_status = v_id_available,
               updated_at = now()
         WHERE lower(s.status) IN ('hold_payment', 'pending')
           AND v_id_available IS NOT NULL
           AND COALESCE(s.updated_at, s.created_at) < now() - interval '5 minutes'
           AND NOT EXISTS (
               SELECT 1
                 FROM schedule_rent_map srm2
                 JOIN reservation.rent r2 ON r2.id_rent = srm2.id_rent
                WHERE srm2.id_schedule = s.id_schedule
                  AND lower(r2.status) NOT IN ('cancelled', 'fullfilled')
           );

        -- 3) Delete orphan schedules that never got linked to any rent.
        DELETE FROM reservation.schedule s
         WHERE s.created_at < now() - interval '6 minutes'
           AND NOT EXISTS (
               SELECT 1
                 FROM reservation.rent_schedule rs
                WHERE rs.id_schedule = s.id_schedule
           )
           AND NOT EXISTS (
               SELECT 1
                 FROM reservation.rent r
                WHERE r.id_schedule = s.id_schedule
           );
    END;
    $$;

    CREATE OR REPLACE FUNCTION reservation.mark_fullfilled_rents()
    RETURNS void
    LANGUAGE plpgsql
    AS $$
    DECLARE
        v_id_fullfilled bigint;
    BEGIN
        SELECT MAX(CASE WHEN lower(code) = 'fullfilled' THEN id_status END)
          INTO v_id_fullfilled
          FROM reservation.status_catalog
         WHERE is_active = true;

        -- 1) Promote reserved rents to fullfilled once finished.
        UPDATE reservation.rent r
           SET status = 'fullfilled',
               id_status = v_id_fullfilled
         WHERE lower(r.status) = 'reserved'
           AND r.finished IS NOT NULL
           AND r.finished < now() - interval '1 minute'
           AND v_id_fullfilled IS NOT NULL;

        -- 2) Sync all linked schedules (combo-safe through rent_schedule).
        WITH schedule_rent_map AS (
            SELECT DISTINCT rs.id_schedule, rs.id_rent
              FROM reservation.rent_schedule rs
            UNION
            SELECT DISTINCT r.id_schedule, r.id_rent
              FROM reservation.rent r
             WHERE r.id_schedule IS NOT NULL
        )
        UPDATE reservation.schedule s
           SET status = 'fullfilled',
               id_status = v_id_fullfilled,
               updated_at = now()
          FROM schedule_rent_map srm
          JOIN reservation.rent r ON r.id_rent = srm.id_rent
         WHERE s.id_schedule = srm.id_schedule
           AND lower(s.status) = 'reserved'
           AND lower(r.status) = 'fullfilled'
           AND v_id_fullfilled IS NOT NULL;
    END;
    $$;

    CREATE OR REPLACE FUNCTION reservation.expire_under_review_after_start()
    RETURNS void
    LANGUAGE plpgsql
    AS $$
    DECLARE
        v_rent_expired_id bigint;
        v_schedule_expired_id bigint;
    BEGIN
        SELECT sc.id_status
          INTO v_rent_expired_id
          FROM reservation.status_catalog sc
         WHERE sc.entity = 'rent'
           AND sc.is_active = true
           AND lower(sc.code) IN ('expired_slot_unavailable', 'expired')
         ORDER BY
             CASE lower(sc.code)
                 WHEN 'expired_slot_unavailable' THEN 1
                 WHEN 'expired' THEN 2
                 ELSE 99
             END,
             sc.id_status DESC
         LIMIT 1;

        SELECT sc.id_status
          INTO v_schedule_expired_id
          FROM reservation.status_catalog sc
         WHERE sc.entity = 'schedule'
           AND sc.is_active = true
           AND lower(sc.code) = 'expired'
         ORDER BY sc.id_status DESC
         LIMIT 1;

        WITH expired_rents AS (
            UPDATE reservation.rent r
               SET status = 'expired',
                   id_status = v_rent_expired_id
             WHERE lower(r.status) = 'under_review'
               AND r.start_time < now()
               AND v_rent_expired_id IS NOT NULL
            RETURNING r.id_rent
        ),
        affected_schedules AS (
            SELECT DISTINCT rs.id_schedule
              FROM reservation.rent_schedule rs
              JOIN expired_rents er ON er.id_rent = rs.id_rent
            UNION
            SELECT DISTINCT r.id_schedule
              FROM reservation.rent r
              JOIN expired_rents er ON er.id_rent = r.id_rent
             WHERE r.id_schedule IS NOT NULL
        )
        UPDATE reservation.schedule s
           SET status = 'expired',
               id_status = v_schedule_expired_id,
               updated_at = now()
         WHERE s.id_schedule IN (SELECT id_schedule FROM affected_schedules)
           AND v_schedule_expired_id IS NOT NULL
           AND lower(s.status) <> 'expired';
    END;
    $$;
    """
    try:
        with engine.begin() as connection:
            connection.execute(text(function_sql))
    except SQLAlchemyError as exc:
        logger.exception("Failed to ensure reservation stored procedures")
        raise RuntimeError("Failed to initialize reservation stored procedures") from exc
