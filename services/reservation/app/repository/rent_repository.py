from __future__ import annotations

from typing import Dict, Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.rent import Rent
from app.models.schedule import Schedule


def list_rents(
    db: Session,
    *,
    status_filter: Optional[str] = None,
    schedule_id: Optional[int] = None,
) -> list[Rent]:
    query = db.query(Rent).options(
        joinedload(Rent.schedule).joinedload(Schedule.field),
        joinedload(Rent.schedule).joinedload(Schedule.user),
    )

    if status_filter is not None:
        query = query.filter(Rent.status == status_filter)
    if schedule_id is not None:
        query = query.filter(Rent.id_schedule == schedule_id)

    return query.order_by(Rent.start_time).all()


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
