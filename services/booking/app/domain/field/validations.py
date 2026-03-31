from __future__ import annotations

from datetime import date

from app.core.error_codes import BOOKING_BAD_REQUEST, BOOKING_NOT_FOUND, http_error
from app.models import Field, Sport
from app.repository import field_repository, sport_repository


def ensure_sport_exists(db, sport_id: int) -> Sport:
    """Verifica que el deporte exista y lo retorna.

    Usado en: FieldService.create_field y FieldService.update_field.
    """
    sport = sport_repository.get_sport(db, sport_id)
    if sport is None:
        raise http_error(
            BOOKING_NOT_FOUND,
            detail=f"Sport {sport_id} not found",
        )
    return sport


def validate_field_entity(field: Field) -> None:
    """Valida reglas internas de la cancha antes de persistir cambios.

    Usado en: FieldService.create_field y FieldService.update_field.
    """
    if field.open_time >= field.close_time:
        raise http_error(
            BOOKING_BAD_REQUEST,
            detail="open_time must be earlier than close_time",
        )
    if field.capacity <= 0:
        raise http_error(
            BOOKING_BAD_REQUEST,
            detail="capacity must be greater than zero",
        )
    if float(field.price_per_hour) <= 0:
        raise http_error(
            BOOKING_BAD_REQUEST,
            detail="price_per_hour must be greater than zero",
        )
    if float(field.minutes_wait) < 0:
        raise http_error(
            BOOKING_BAD_REQUEST,
            detail="minutes_wait must be zero or greater",
        )


def ensure_field_deletable(db, field: Field, reference_date: date) -> None:
    """Valida que la cancha pueda eliminarse sin reservas futuras.

    Usado en: FieldService.delete_field.
    """
    if (field.status or "").lower() == "occupied":
        raise http_error(
            BOOKING_BAD_REQUEST,
            detail="Cannot delete a field while its status is 'occupied'",
        )

    if field_repository.field_has_upcoming_reservations(
        db, field.id_field, reference_date=reference_date
    ):
        raise http_error(
            BOOKING_BAD_REQUEST,
            detail=(
                "Cannot delete a field with reserved or pending schedules today or later"
            ),
        )
