from __future__ import annotations

from datetime import date
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models import Field, Schedule, Sport


def list_fields_by_campus(db: Session, campus_id: int) -> List[Field]:
    return (
        db.query(Field)
        .options(
            selectinload(Field.sport).selectinload(Sport.modality),
            selectinload(Field.images),
        )
        .filter(Field.id_campus == campus_id)
        .order_by(Field.id_field)
        .all()
    )

def get_field(db: Session, field_id: int) -> Optional[Field]:
    return (
        db.query(Field)
        .options(
            selectinload(Field.sport).selectinload(Sport.modality),
            selectinload(Field.images),
        )
        .filter(Field.id_field == field_id)
        .first()
    )


def create_field(db: Session, field: Field) -> Field:
    db.add(field)
    db.flush()
    return field


def delete_field(db: Session, field: Field) -> None:
    db.delete(field)


def field_has_upcoming_reservations(
    db: Session,
    field_id: int,
    *,
    reference_date: date,
) -> bool:
    """Return True when the field has reserved or pending schedules today or later."""

    statuses = ("reserved", "pending")
    match = (
        db.query(Schedule.id_schedule)
        .filter(
            Schedule.id_field == field_id,
            func.lower(Schedule.status).in_(statuses),
            func.date(Schedule.start_time) >= reference_date,
        )
        .first()
    )
    return match is not None
