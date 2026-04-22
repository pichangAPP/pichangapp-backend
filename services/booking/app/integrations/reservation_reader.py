"""Read-only access to reservation schema data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable, List, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.weekly_schedule_closure_overlap import (
    WeeklyClosureRule,
    utc_interval_overlaps_weekly_closures,
)


@dataclass(frozen=True)
class ScheduleSummary:
    id_schedule: int
    id_field: int
    day_of_week: str
    start_time: datetime
    end_time: datetime
    price: Decimal
    status: str


def _weekly_closure_rules_by_field(
    db: Session,
    field_ids: list[int],
) -> dict[int, List[WeeklyClosureRule]]:
    if not field_ids:
        return {}
    query = text(
        """
        SELECT f.id_field AS applies_field, c.weekday, c.local_start_time, c.local_end_time
        FROM booking.weekly_schedule_closure c
        JOIN booking.field f ON f.id_campus = c.id_campus
        WHERE c.is_active = true
          AND f.id_field IN :field_ids
          AND (c.id_field IS NULL OR c.id_field = f.id_field)
        """
    ).bindparams(bindparam("field_ids", expanding=True))
    rows = db.execute(query, {"field_ids": field_ids}).mappings().all()
    out: dict[int, List[WeeklyClosureRule]] = {}
    for row in rows:
        fid = int(row["applies_field"])
        out.setdefault(fid, []).append(
            WeeklyClosureRule(
                int(row["weekday"]),
                row["local_start_time"],
                row["local_end_time"],
            )
        )
    return out


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
    rules_by_field = _weekly_closure_rules_by_field(db, ids)
    summaries = [ScheduleSummary(**row) for row in rows]
    return [
        s
        for s in summaries
        if not utc_interval_overlaps_weekly_closures(
            s.start_time,
            s.end_time,
            rules_by_field.get(s.id_field, ()),
            tz_name=settings.TIMEZONE,
        )
    ]


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
          AND DATE(start_time AT TIME ZONE :timezone) = :target_date
        ORDER BY start_time
        """
    ).bindparams(bindparam("field_ids", expanding=True))

    rows = db.execute(
        query,
        {"field_ids": ids, "target_date": target_date, "timezone": settings.TIMEZONE},
    ).mappings().all()
    rules_by_field = _weekly_closure_rules_by_field(db, ids)
    summaries = [ScheduleSummary(**row) for row in rows]
    return [
        s
        for s in summaries
        if not utc_interval_overlaps_weekly_closures(
            s.start_time,
            s.end_time,
            rules_by_field.get(s.id_field, ()),
            tz_name=settings.TIMEZONE,
        )
    ]


def list_reserved_rent_time_windows_for_fields(
    db: Session,
    field_ids: list[int],
) -> list[tuple[int, datetime, datetime]]:
    """Rent rows in ``reserved`` status (not ended) touching any of ``field_ids`` (primary or M:N schedule)."""
    if not field_ids:
        return []
    query = text(
        """
        SELECT DISTINCT r.id_rent, r.start_time, r.end_time
          FROM reservation.rent r
         WHERE lower(trim(r.status)) = 'reserved'
           AND r.start_time IS NOT NULL
           AND r.end_time IS NOT NULL
           AND r.end_time >= now()
           AND (
                EXISTS (
                    SELECT 1
                      FROM reservation.schedule s
                     WHERE s.id_schedule = r.id_schedule
                       AND s.id_field IN :field_ids
                )
                OR EXISTS (
                    SELECT 1
                      FROM reservation.rent_schedule rs
                      JOIN reservation.schedule s ON s.id_schedule = rs.id_schedule
                     WHERE rs.id_rent = r.id_rent
                       AND s.id_field IN :field_ids
                )
           )
        """
    ).bindparams(bindparam("field_ids", expanding=True))
    rows = db.execute(query, {"field_ids": field_ids}).mappings().all()
    out: list[tuple[int, datetime, datetime]] = []
    for row in rows:
        rid = int(row["id_rent"])
        st = row["start_time"]
        en = row["end_time"]
        if st is not None and en is not None:
            out.append((rid, st, en))
    return out


def find_reserved_rent_id_conflicting_with_weekly_rule(
    db: Session,
    *,
    field_ids: list[int],
    rule: WeeklyClosureRule,
) -> Optional[int]:
    """Return ``id_rent`` of a reserved rent whose window overlaps the recurring closure, or ``None``."""
    for rid, st, en in list_reserved_rent_time_windows_for_fields(db, field_ids):
        if utc_interval_overlaps_weekly_closures(
            st,
            en,
            [rule],
            tz_name=settings.TIMEZONE,
        ):
            return rid
    return None


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
          AND DATE(start_time AT TIME ZONE :timezone) >= :reference_date
        LIMIT 1
        """
    ).bindparams(bindparam("statuses", expanding=True))

    result = db.execute(
        query,
        {
            "field_id": field_id,
            "statuses": status_values,
            "reference_date": reference_date,
            "timezone": settings.TIMEZONE,
        },
    ).scalar_one_or_none()
    return result is not None


__all__ = [
    "ScheduleSummary",
    "field_has_upcoming_reservations",
    "find_reserved_rent_id_conflicting_with_weekly_rule",
    "get_available_schedules",
    "get_schedules_for_fields_on_date",
    "list_reserved_rent_time_windows_for_fields",
]
