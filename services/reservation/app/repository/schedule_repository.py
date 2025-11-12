from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Iterable, Sequence

from sqlalchemy import exists, func
from sqlalchemy.orm import Session, joinedload, load_only

from app.models.campus import Campus
from app.models.field import Field
from app.models.rent import Rent
from app.models.user import User
from app.models.schedule import Schedule


def get_schedule(db: Session, schedule_id: int) -> Optional[Schedule]:
    return (
        db.query(Schedule)
        .options(
            joinedload(Schedule.field)
            .joinedload(Field.campus)
            .joinedload(Campus.manager),
            joinedload(Schedule.user),
        )
        .filter(Schedule.id_schedule == schedule_id)
        .first()
    )

def list_schedules(
    db: Session,
    *,
    field_id: Optional[int] = None,
    day_of_week: Optional[str] = None,
    status_filter: Optional[str] = None,
) -> list[Schedule]:
    query = db.query(Schedule).options(
        joinedload(Schedule.field)
        .joinedload(Field.campus)
        .joinedload(Campus.manager),
        joinedload(Schedule.user),
    )

    if field_id is not None:
        query = query.filter(Schedule.id_field == field_id)
    if day_of_week is not None:
        query = query.filter(Schedule.day_of_week == day_of_week)
    if status_filter is not None:
        query = query.filter(Schedule.status == status_filter)

    return query.order_by(Schedule.start_time.desc(), Schedule.end_time.desc()).all()


def create_schedule(db: Session, schedule_data: dict) -> Schedule:
    schedule = Schedule(**schedule_data)
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


def save_schedule(db: Session, schedule: Schedule) -> Schedule:
    db.flush()
    db.commit()
    db.refresh(schedule)
    return schedule


def delete_schedule(db: Session, schedule: Schedule) -> None:
    db.delete(schedule)
    db.commit()


def field_has_schedule_in_range(
    db: Session,
    *,
    field_id: int,
    start_time: datetime,
    end_time: datetime,
    status_filter: Optional[Sequence[str]] = None,
    exclude_schedule_id: Optional[int] = None,
    exclude_statuses: Optional[Sequence[str]] = None,
) -> bool:
    """Return ``True`` when a field has schedules in the requested range."""

    query = (
        db.query(Schedule.id_schedule)
        .filter(Schedule.id_field == field_id)
        .filter(Schedule.start_time < end_time)
        .filter(Schedule.end_time > start_time)
    )

    if exclude_schedule_id is not None:
        query = query.filter(Schedule.id_schedule != exclude_schedule_id)

    normalized_statuses = [
        status_value.strip().lower()
        for status_value in (status_filter or ())
        if status_value and status_value.strip()
    ]

    if normalized_statuses:
        query = query.filter(func.lower(Schedule.status).in_(normalized_statuses))

    normalized_excluded = [
        status_value.strip().lower()
        for status_value in (exclude_statuses or ())
        if status_value and status_value.strip()
    ]

    if normalized_excluded:
        query = query.filter(~func.lower(Schedule.status).in_(normalized_excluded))

    return query.first() is not None

def list_available_schedules(
    db: Session,
    *,
    field_id: int,
    day_of_week: Optional[str] = None,
    status_filter: Optional[str] = None,
    exclude_rent_statuses: Optional[Sequence[str]] = None,
) -> list[Schedule]:
    query = db.query(Schedule).options(
        joinedload(Schedule.field)
        .joinedload(Field.campus)
        .joinedload(Campus.manager),
        joinedload(Schedule.user),
    )

    query = query.filter(Schedule.id_field == field_id)

    if day_of_week is not None:
        query = query.filter(Schedule.day_of_week == day_of_week)
    if status_filter is not None:
        query = query.filter(Schedule.status == status_filter)

    excluded_statuses: Iterable[str] = [
        status_value
        for status_value in (exclude_rent_statuses or ("cancelled",))
        if status_value
    ]

    active_rent_exists = exists().where(
        Rent.id_schedule == Schedule.id_schedule,
    )

    if excluded_statuses:
        active_rent_exists = active_rent_exists.where(
            Rent.status.notin_(excluded_statuses)
        )

    query = query.filter(~active_rent_exists)

    return query.order_by(Schedule.start_time).all()


def list_schedules_by_date(
    db: Session,
    *,
    field_id: int,
    target_date: date,
) -> list[Schedule]:
    return (
        db.query(Schedule)
        .options(
            load_only(
                Schedule.id_schedule,
                Schedule.start_time,
                Schedule.end_time,
                Schedule.status,
                Schedule.price
            )
        )
        .filter(Schedule.id_field == field_id)
        .filter(func.date(Schedule.start_time) == target_date)
        .order_by(Schedule.start_time)
        .all()
    )


def get_field(db: Session, field_id: int) -> Optional[Field]:
    return db.query(Field).filter(Field.id_field == field_id).first()


def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id_user == user_id).first()
