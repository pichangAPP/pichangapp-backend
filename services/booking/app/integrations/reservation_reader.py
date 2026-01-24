"""Read-only access to reservation schema data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class ScheduleSummary:
    id_schedule: int
    id_field: int
    day_of_week: str
    start_time: datetime
    end_time: datetime
    price: Decimal
    status: str


def get_available_schedules(
    db: Session,
    field_ids: Iterable[int],
    *,
    start_time: datetime,
    status: str = "available",
) -> list[ScheduleSummary]:
    ids = [field_id for field_id in field_ids if field_id is not None]
    if not ids:
        return []

    query = text(
        """
        SELECT id_schedule, id_field, day_of_week, start_time, end_time, price, status
        FROM reservation.schedule
        WHERE id_field IN :field_ids
          AND start_time >= :start_time
          AND lower(status) = :status
        ORDER BY start_time
        """
    ).bindparams(bindparam("field_ids", expanding=True))

    rows = db.execute(
        query,
        {
            "field_ids": ids,
            "start_time": start_time,
            "status": status.lower(),
        },
    ).mappings().all()
    return [ScheduleSummary(**row) for row in rows]


def get_schedules_for_fields_on_date(
    db: Session,
    field_ids: Iterable[int],
    *,
    target_date: date,
) -> list[ScheduleSummary]:
    ids = [field_id for field_id in field_ids if field_id is not None]
    if not ids:
        return []

    query = text(
        """
        SELECT id_schedule, id_field, day_of_week, start_time, end_time, price, status
        FROM reservation.schedule
        WHERE id_field IN :field_ids
          AND DATE(start_time) = :target_date
        ORDER BY start_time
        """
    ).bindparams(bindparam("field_ids", expanding=True))

    rows = db.execute(
        query,
        {"field_ids": ids, "target_date": target_date},
    ).mappings().all()
    return [ScheduleSummary(**row) for row in rows]


def field_has_upcoming_reservations(
    db: Session,
    field_id: int,
    *,
    reference_date: date,
    statuses: Iterable[str],
) -> bool:
    status_values = [status.lower() for status in statuses if status]
    if not status_values:
        return False

    query = text(
        """
        SELECT 1
        FROM reservation.schedule
        WHERE id_field = :field_id
          AND lower(status) IN :statuses
          AND DATE(start_time) >= :reference_date
        LIMIT 1
        """
    ).bindparams(bindparam("statuses", expanding=True))

    result = db.execute(
        query,
        {
            "field_id": field_id,
            "statuses": status_values,
            "reference_date": reference_date,
        },
    ).scalar_one_or_none()
    return result is not None


__all__ = [
    "ScheduleSummary",
    "field_has_upcoming_reservations",
    "get_available_schedules",
    "get_schedules_for_fields_on_date",
]
