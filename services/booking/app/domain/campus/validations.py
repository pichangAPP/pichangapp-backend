from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.error_codes import BOOKING_BAD_REQUEST, BOOKING_NOT_FOUND, http_error
from app.models import Campus
from app.repository import sport_repository
from app.schemas import CampusCreate


def validate_campus_fields(db: Session, campus_in: CampusCreate) -> None:
    """Verifica que los deportes de los campos existan en el catalogo.

    Usado en: CampusService.create_campus y BusinessService.create_business.
    """
    missing_sports = {
        field_in.id_sport
        for field_in in campus_in.fields
        if sport_repository.get_sport(db, field_in.id_sport) is None
    }
    if missing_sports:
        missing_list = ", ".join(str(sport_id) for sport_id in sorted(missing_sports))
        raise http_error(
            BOOKING_NOT_FOUND,
            detail=f"Sports not found for ids: {missing_list}",
        )


def validate_campus_entity(campus: Campus) -> None:
    """Valida reglas internas del campus antes de persistir cambios.

    Usado en: CampusService.create_campus y CampusService.update_campus.
    """
    if campus.opentime >= campus.closetime:
        raise http_error(
            BOOKING_BAD_REQUEST,
            detail="opentime must be earlier than closetime",
        )
    if campus.count_fields < 0:
        raise http_error(
            BOOKING_BAD_REQUEST,
            detail="count_fields must be zero or positive",
        )
    if not (0 <= float(campus.rating) <= 10):
        raise http_error(
            BOOKING_BAD_REQUEST,
            detail="rating must be between 0 and 10",
        )
