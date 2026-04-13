"""Validation for combined-field (multi-schedule) rents."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Sequence

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.schedule import Schedule
from app.repository import rent_repository
from app.domain.rent.validations import get_schedule


def compute_combo_mount(*, price_per_hour: Decimal, start_time: datetime, end_time: datetime) -> Decimal:
    from app.domain.rent.defaults import calculate_minutes

    minutes = calculate_minutes(start_time=start_time, end_time=end_time)
    hour_fraction = minutes / Decimal(60)
    return (price_per_hour * hour_fraction).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def validate_combo_schedules(
    db: Session,
    *,
    member_field_ids: Sequence[int],
    schedule_ids: Sequence[int],
    excluded_rent_statuses: Sequence[str],
) -> List[Schedule]:
    """Return schedules ordered by ``member_field_ids``; raises if invalid."""
    if len(schedule_ids) != len(set(schedule_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate schedule in combination request",
        )
    if len(schedule_ids) != len(member_field_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Schedule count must match combination field count",
        )

    schedules: List[Schedule] = [get_schedule(db, sid) for sid in schedule_ids]
    by_field: dict[int, Schedule] = {}
    for sch in schedules:
        if sch.id_field is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Each schedule must be linked to a field",
            )
        if sch.id_field in by_field:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Multiple schedules for the same field in combination request",
            )
        by_field[sch.id_field] = sch

    if set(by_field.keys()) != set(member_field_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Schedules must cover exactly the combination's fields",
        )

    ref_start = schedules[0].start_time
    ref_end = schedules[0].end_time
    ref_day = schedules[0].day_of_week
    for sch in schedules[1:]:
        if sch.start_time != ref_start or sch.end_time != ref_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="All combined schedules must share the same time window",
            )
        if sch.day_of_week != ref_day:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="All combined schedules must share the same day",
            )

    ordered = [by_field[fid] for fid in member_field_ids]

    for sch in ordered:
        if rent_repository.schedule_has_active_rent(
            db,
            sch.id_schedule,
            excluded_statuses=list(excluded_rent_statuses),
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Schedule {sch.id_schedule} already has an active rent",
            )

    return ordered


__all__ = ["compute_combo_mount", "validate_combo_schedules"]
