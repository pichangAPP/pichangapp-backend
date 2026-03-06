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


def ensure_reservation_functions() -> None:
    function_sql = """
    DROP FUNCTION IF EXISTS reservation.get_rents_by_campus(bigint, text);

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
        user_status varchar
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
               u.status
        FROM reservation.rent r
        JOIN reservation.schedule s ON s.id_schedule = r.id_schedule
        JOIN booking.field f ON f.id_field = s.id_field
        LEFT JOIN auth.users u ON u.id_user = s.id_user
        WHERE f.id_campus = p_campus_id
          AND (p_status IS NULL OR r.status = p_status)
        ORDER BY r.date_create DESC;
    END;
    $$;
    """
    try:
        with engine.begin() as connection:
            connection.execute(text(function_sql))
    except SQLAlchemyError as exc:
        logger.exception("Failed to ensure reservation stored procedures")
        raise RuntimeError("Failed to initialize reservation stored procedures") from exc
