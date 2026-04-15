from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, Optional, Sequence, Set

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session, joinedload

from app.models.rent import Rent
from app.models.rent_schedule import RentSchedule
from app.models.schedule import Schedule


def _rent_load_options():
    return (
        joinedload(Rent.schedule),
        joinedload(Rent.schedule_links).joinedload(RentSchedule.schedule),
    )


def list_rents(
    db: Session,
    *,
    status_filter: Optional[str] = None,
    exclude_status: Optional[str] = None,
    schedule_id: Optional[int] = None,
    field_id: Optional[int] = None,
    field_ids: Optional[Sequence[int]] = None,
    user_id: Optional[int] = None,
    order_by_created: bool = False,
    sort_desc: bool = False,
) -> list[Rent]:
    query = db.query(Rent).options(*_rent_load_options())

    if status_filter is not None:
        query = query.filter(Rent.status == status_filter)
    if exclude_status:
        query = query.filter(
            func.lower(Rent.status) != func.lower(exclude_status.strip())
        )
    if schedule_id is not None:
        query = query.filter(
            or_(
                Rent.id_schedule == schedule_id,
                Rent.id_rent.in_(
                    select(RentSchedule.id_rent).where(RentSchedule.id_schedule == schedule_id)
                ),
            )
        )
    if field_id is not None:
        query = query.filter(
            or_(
                Rent.id_schedule.in_(select(Schedule.id_schedule).where(Schedule.id_field == field_id)),
                Rent.id_rent.in_(
                    select(RentSchedule.id_rent)
                    .join(Schedule, Schedule.id_schedule == RentSchedule.id_schedule)
                    .where(Schedule.id_field == field_id)
                ),
            )
        )
    if field_ids:
        query = query.filter(
            or_(
                Rent.id_schedule.in_(select(Schedule.id_schedule).where(Schedule.id_field.in_(field_ids))),
                Rent.id_rent.in_(
                    select(RentSchedule.id_rent)
                    .join(Schedule, Schedule.id_schedule == RentSchedule.id_schedule)
                    .where(Schedule.id_field.in_(field_ids))
                ),
            )
        )
    if user_id is not None:
        query = query.filter(
            or_(
                Rent.id_schedule.in_(select(Schedule.id_schedule).where(Schedule.id_user == user_id)),
                Rent.id_rent.in_(
                    select(RentSchedule.id_rent)
                    .join(Schedule, Schedule.id_schedule == RentSchedule.id_schedule)
                    .where(Schedule.id_user == user_id)
                ),
            )
        )

    if order_by_created:
        order_clause = Rent.date_create.desc() if sort_desc else Rent.date_create
    else:
        order_clause = Rent.start_time.desc() if sort_desc else Rent.start_time

    return query.order_by(order_clause).all()


def list_rents_by_campus_view(
    db: Session,
    *,
    campus_id: int,
    status_filter: Optional[str] = None,
    exclude_status: Optional[str] = None,
) -> list[dict]:
    query = text(
        """
        SELECT *
        FROM reservation.get_rents_by_campus(:campus_id, :status_filter)
        """
    )
    rows = db.execute(
        query,
        {
            "campus_id": campus_id,
            "status_filter": status_filter,
        },
    ).mappings().all()
    out = [dict(row) for row in rows]
    if exclude_status:
        ex = exclude_status.strip().lower()
        out = [
            row
            for row in out
            if (row.get("status") or "").lower() != ex
        ]
    return out


def get_rent(db: Session, rent_id: int) -> Optional[Rent]:
    return (
        db.query(Rent)
        .options(*_rent_load_options())
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
    query = db.query(Rent).filter(
        or_(
            Rent.id_schedule == schedule_id,
            Rent.id_rent.in_(
                select(RentSchedule.id_rent).where(RentSchedule.id_schedule == schedule_id)
            ),
        )
    )

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


def create_rent_with_schedule_links(
    db: Session,
    rent_data: Dict[str, object],
    schedule_links: Sequence[tuple[int, bool]],
) -> Rent:
    """Create a rent and M:N schedule rows in one transaction."""
    rent = Rent(**rent_data)
    db.add(rent)
    db.flush()
    for schedule_id, is_primary in schedule_links:
        db.add(
            RentSchedule(
                id_rent=rent.id_rent,
                id_schedule=schedule_id,
                is_primary=is_primary,
            )
        )
    db.commit()
    db.refresh(rent)
    return rent


def add_rent_schedule_link(
    db: Session,
    *,
    rent_id: int,
    schedule_id: int,
    is_primary: bool,
) -> None:
    db.add(
        RentSchedule(
            id_rent=rent_id,
            id_schedule=schedule_id,
            is_primary=is_primary,
        )
    )
    db.commit()


def sync_primary_schedule_link(
    db: Session,
    *,
    rent_id: int,
    new_schedule_id: int,
) -> None:
    """Keep a single rent_schedule row in sync when the primary schedule id changes."""
    links = db.query(RentSchedule).filter(RentSchedule.id_rent == rent_id).all()
    if len(links) > 1:
        return
    if links:
        links[0].id_schedule = new_schedule_id
        links[0].is_primary = True
    else:
        db.add(
            RentSchedule(
                id_rent=rent_id,
                id_schedule=new_schedule_id,
                is_primary=True,
            )
        )
    db.commit()


def list_schedule_ids_for_rent(db: Session, rent_id: int) -> list[int]:
    rows = (
        db.query(RentSchedule.id_schedule, RentSchedule.is_primary)
        .filter(RentSchedule.id_rent == rent_id)
        .order_by(RentSchedule.is_primary.desc(), RentSchedule.id_schedule)
        .all()
    )
    return [r[0] for r in rows]


def save_rent(db: Session, rent: Rent) -> Rent:
    db.flush()
    db.commit()
    db.refresh(rent)
    return rent


def delete_rent(db: Session, rent: Rent) -> None:
    db.delete(rent)
    db.commit()


def _status_filter_clause(excluded_statuses: Iterable[str]):
    filtered_statuses = [
        status_value.lower()
        for status_value in excluded_statuses
        if status_value
    ]
    if not filtered_statuses:
        return None
    return func.lower(Rent.status).notin_(filtered_statuses)


def field_has_pending_rent(
    db: Session,
    field_id: int,
    *,
    excluded_statuses: Iterable[str] = (),
) -> bool:
    status_clause = _status_filter_clause(excluded_statuses)

    q1 = (
        db.query(Rent.id_rent)
        .join(Schedule, Schedule.id_schedule == Rent.id_schedule)
        .filter(Schedule.id_field == field_id, Rent.end_time > func.now())
    )
    if status_clause is not None:
        q1 = q1.filter(status_clause)
    if q1.first() is not None:
        return True

    q2 = (
        db.query(Rent.id_rent)
        .select_from(Rent)
        .join(RentSchedule, RentSchedule.id_rent == Rent.id_rent)
        .join(Schedule, Schedule.id_schedule == RentSchedule.id_schedule)
        .filter(Schedule.id_field == field_id, Rent.end_time > func.now())
    )
    if status_clause is not None:
        q2 = q2.filter(status_clause)
    return q2.first() is not None


def _rent_ids_tied_to_schedule(db: Session, schedule_id: int) -> Set[int]:
    ids: Set[int] = {
        row[0]
        for row in db.query(Rent.id_rent).filter(Rent.id_schedule == schedule_id).all()
    }
    ids.update(
        row[0]
        for row in db.query(RentSchedule.id_rent)
        .filter(RentSchedule.id_schedule == schedule_id)
        .all()
    )
    return ids


def field_has_active_rent_in_range(
    db: Session,
    *,
    field_id: int,
    start_time: datetime,
    end_time: datetime,
    excluded_statuses: Optional[Sequence[str]] = None,
    exclude_schedule_id: Optional[int] = None,
) -> bool:
    excluded_rent_ids: Set[int] = set()
    if exclude_schedule_id is not None:
        excluded_rent_ids = _rent_ids_tied_to_schedule(db, exclude_schedule_id)

    status_clause = _status_filter_clause(excluded_statuses or ())

    def base_time_filters(q):
        q = q.filter(Rent.start_time < end_time, Rent.end_time > start_time)
        if status_clause is not None:
            q = q.filter(status_clause)
        if excluded_rent_ids:
            q = q.filter(~Rent.id_rent.in_(excluded_rent_ids))
        return q

    q1 = base_time_filters(
        db.query(Rent.id_rent).join(Schedule, Schedule.id_schedule == Rent.id_schedule).filter(
            Schedule.id_field == field_id,
        )
    )
    if q1.first() is not None:
        return True

    q2 = base_time_filters(
        db.query(Rent.id_rent)
        .select_from(Rent)
        .join(RentSchedule, RentSchedule.id_rent == Rent.id_rent)
        .join(Schedule, Schedule.id_schedule == RentSchedule.id_schedule)
        .filter(Schedule.id_field == field_id)
    )
    return q2.first() is not None


def get_active_schedule_ids(
    db: Session,
    schedule_ids: Sequence[int],
    *,
    excluded_statuses: Optional[Sequence[str]] = None,
) -> Set[int]:
    if not schedule_ids:
        return set()

    filtered_statuses = [
        status_value.lower()
        for status_value in (excluded_statuses or ())
        if status_value
    ]

    q1 = db.query(Rent.id_schedule).filter(Rent.id_schedule.in_(schedule_ids))
    q2 = (
        db.query(RentSchedule.id_schedule)
        .join(Rent, Rent.id_rent == RentSchedule.id_rent)
        .filter(RentSchedule.id_schedule.in_(schedule_ids))
    )
    if filtered_statuses:
        q1 = q1.filter(func.lower(Rent.status).notin_(filtered_statuses))
        q2 = q2.filter(func.lower(Rent.status).notin_(filtered_statuses))

    out: Set[int] = {row[0] for row in q1.distinct().all() if row[0] is not None}
    out.update(row[0] for row in q2.distinct().all())
    return out
