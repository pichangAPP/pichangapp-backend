from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, Optional, Sequence, Set

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.field import Field
from app.models.rent import Rent
from app.models.schedule import Schedule


def list_rents(
    db: Session,
    *,
    status_filter: Optional[str] = None,
    schedule_id: Optional[int] = None,
    field_id: Optional[int] = None,
    user_id: Optional[int] = None,
    sort_desc: bool = False,
    campus_id: Optional[int] = None,
) -> list[Rent]:
    query = db.query(Rent).options(
        joinedload(Rent.schedule).joinedload(Schedule.field),
        joinedload(Rent.schedule).joinedload(Schedule.user),
    )

    if field_id is not None or user_id is not None or campus_id is not None:
        query = query.join(Rent.schedule)
    if campus_id is not None:
        query = query.join(Schedule.field)

    if status_filter is not None:
        query = query.filter(Rent.status == status_filter)
    if schedule_id is not None:
        query = query.filter(Rent.id_schedule == schedule_id)
    if field_id is not None:
        query = query.filter(Schedule.id_field == field_id)
    if user_id is not None:
        query = query.filter(Schedule.id_user == user_id)
    if campus_id is not None:
        query = query.filter(Field.id_campus == campus_id)

    order_clause = Rent.start_time.desc() if sort_desc else Rent.start_time

    return query.order_by(order_clause).all()


def get_rent(db: Session, rent_id: int) -> Optional[Rent]:
    return (
        db.query(Rent)
        .options(
            joinedload(Rent.schedule).joinedload(Schedule.field),
            joinedload(Rent.schedule).joinedload(Schedule.user),
        )
        .filter(Rent.id_rent == rent_id)
        .first()
    )


def schedule_has_active_rent(
    db: Session,
    schedule_id: int,
    *,
    excluded_statuses: Iterable[str] = (),
    exclude_rent_id: Optional[int] = None,
) -> bool:
    query = db.query(Rent).filter(Rent.id_schedule == schedule_id)

    if exclude_rent_id is not None:
        query = query.filter(Rent.id_rent != exclude_rent_id)

    filtered_statuses = [
        status_value.lower()
        for status_value in excluded_statuses
        if status_value
    ]

    if filtered_statuses:
        query = query.filter(func.lower(Rent.status).notin_(filtered_statuses))

    return query.first() is not None


def create_rent(db: Session, rent_data: Dict[str, object]) -> Rent:
    rent = Rent(**rent_data)
    db.add(rent)
    db.commit()
    db.refresh(rent)
    return rent


def save_rent(db: Session, rent: Rent) -> Rent:
    db.flush()
    db.commit()
    db.refresh(rent)
    return rent


def delete_rent(db: Session, rent: Rent) -> None:
    db.delete(rent)
    db.commit()


def field_has_pending_rent(
    db: Session,
    field_id: int,
    *,
    excluded_statuses: Iterable[str] = (),
) -> bool:
    query = (
        db.query(Rent.id_rent)
        .join(Schedule)
        .filter(Schedule.id_field == field_id)
        .filter(Rent.end_time > func.now())
    )

    filtered_statuses = [
        status_value.lower()
        for status_value in excluded_statuses
        if status_value
    ]

    if filtered_statuses:
        query = query.filter(func.lower(Rent.status).notin_(filtered_statuses))

    return query.first() is not None


def field_has_active_rent_in_range(
    db: Session,
    *,
    field_id: int,
    start_time: datetime,
    end_time: datetime,
    excluded_statuses: Optional[Sequence[str]] = None,
    exclude_schedule_id: Optional[int] = None,
) -> bool:
    query = (
        db.query(Rent.id_rent)
        .join(Schedule)
        .filter(Schedule.id_field == field_id)
        .filter(Rent.start_time < end_time)
        .filter(Rent.end_time > start_time)
    )

    if exclude_schedule_id is not None:
        query = query.filter(Rent.id_schedule != exclude_schedule_id)

    filtered_statuses = [
        status_value.lower()
        for status_value in (excluded_statuses or ())
        if status_value
    ]

    if filtered_statuses:
        query = query.filter(func.lower(Rent.status).notin_(filtered_statuses))

    return query.first() is not None

def get_active_schedule_ids(
    db: Session,
    schedule_ids: Sequence[int],
    *,
    excluded_statuses: Optional[Sequence[str]] = None,
) -> Set[int]:
    if not schedule_ids:
        return set()

    query = db.query(Rent.id_schedule).filter(Rent.id_schedule.in_(schedule_ids))

    filtered_statuses = [
        status_value.lower()
        for status_value in (excluded_statuses or ())
        if status_value
    ]

    if filtered_statuses:
        query = query.filter(func.lower(Rent.status).notin_(filtered_statuses))

    return {row[0] for row in query.distinct()}