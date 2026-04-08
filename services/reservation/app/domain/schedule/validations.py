"""Schedule validation helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.error_codes import (
    FIELD_NOT_FOUND,
    RENT_ACTIVE_CONFLICT,
    SCHEDULE_CONFLICT,
    SCHEDULE_CROSS_DAY,
    SCHEDULE_DURATION_NOT_HOURS,
    SCHEDULE_INVALID_TIME_RANGE,
    SCHEDULE_OUTSIDE_OPENING_HOURS,
    SCHEDULE_PAST_START,
    SCHEDULE_TIME_ALIGNMENT,
    USER_NOT_FOUND,
    http_error,
)
from app.integrations import auth_reader, booking_reader
from app.repository import rent_repository, schedule_repository
from app.schemas.schedule import FieldSummary, UserSummary


def get_field(db: Session, field_id: int) -> FieldSummary:
    """Fetch field summary or raise if missing.

    Used by: ScheduleService create/update/list slots.
    """
    field = booking_reader.get_field_summary(db, field_id)
    if field is None:
        raise http_error(
            FIELD_NOT_FOUND,
            detail="Associated field not found",
        )
    return field


def get_user(db: Session, user_id: int) -> UserSummary:
    """Fetch user summary or raise if missing.

    Used by: ScheduleService create/update.
    """
    try:
        user = auth_reader.get_user_summary(db, user_id)
    except auth_reader.AuthReaderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    if user is None:
        raise http_error(
            USER_NOT_FOUND,
            detail="Associated user not found",
        )
    return user


def ensure_start_time_in_future(start_time: datetime) -> None:
    """Ensure the schedule start is in the future.

    Used by: ScheduleService create.
    """
    local_tz = _get_local_tz()
    now_local = datetime.now(local_tz)
    if start_time.tzinfo is None:
        start_local = start_time.replace(tzinfo=local_tz)
    else:
        start_local = start_time.astimezone(local_tz)

    if start_local <= now_local:
        raise http_error(
            SCHEDULE_PAST_START,
            detail="start_time must be in the future",
        )


def validate_schedule_window(
    *, field: FieldSummary, start_time: datetime, end_time: datetime
) -> None:
    """Validate schedule boundaries and slot alignment.

    Used by: ScheduleService create/update.
    """
    # Validar rango básico.
    if end_time <= start_time:
        raise http_error(
            SCHEDULE_INVALID_TIME_RANGE,
            detail="end_time must be after start_time",
        )

    # No permitimos cruzar al día siguiente (por ahora).
    if end_time.date() != start_time.date():
        raise http_error(
            SCHEDULE_CROSS_DAY,
            detail="Schedules cannot cross over to the next day",
        )

    start_time_value = start_time.time()
    end_time_value = end_time.time()

    # Validación de horario considerando cierres post medianoche.
    # Horario normal (mismo día): open < close.
    if field.close_time > field.open_time:
        if start_time_value < field.open_time or end_time_value > field.close_time:
            raise http_error(
                SCHEDULE_OUTSIDE_OPENING_HOURS,
                detail=(
                    "Schedule must be within the field opening hours"
                    f" ({field.open_time} - {field.close_time})"
                ),
            )
    else:
        # Ventana nocturna: abierto desde open_time hasta medianoche
        # y desde 00:00 hasta close_time del día siguiente.
        is_in_late_segment = start_time_value >= field.open_time
        is_in_early_segment = end_time_value <= field.close_time
        if not (is_in_late_segment or is_in_early_segment):
            raise http_error(
                SCHEDULE_OUTSIDE_OPENING_HOURS,
                detail=(
                    "Schedule must be within the field opening hours"
                    f" ({field.open_time} - {field.close_time})"
                ),
            )

    anchor_minutes = field.open_time.minute
    anchor_seconds = field.open_time.second
    if (
        start_time_value.minute != anchor_minutes
        or start_time_value.second != anchor_seconds
        or end_time_value.minute != anchor_minutes
        or end_time_value.second != anchor_seconds
    ):
        raise http_error(
            SCHEDULE_TIME_ALIGNMENT,
            detail=(
                "Schedule start/end times must align with the field opening time "
                f"minute/second ({field.open_time.strftime('%H:%M:%S')})"
            ),
        )

    duration_seconds = int((end_time - start_time).total_seconds())
    if duration_seconds % 3600 != 0:
        raise http_error(
            SCHEDULE_DURATION_NOT_HOURS,
            detail="Schedule duration must be a whole number of hours",
        )


def ensure_field_not_reserved(
    db: Session,
    *,
    field_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_schedule_id: Optional[int],
    excluded_schedule_statuses: Sequence[str],
    excluded_rent_statuses: Sequence[str],
) -> None:
    """Ensure there is no conflicting schedule or active rent.

    Used by: ScheduleService create/update.
    """
    has_conflicting_schedule = schedule_repository.field_has_schedule_in_range(
        db,
        field_id=field_id,
        start_time=start_time,
        end_time=end_time,
        exclude_schedule_id=exclude_schedule_id,
        exclude_statuses=excluded_schedule_statuses,
    )

    if has_conflicting_schedule:
        raise http_error(
            SCHEDULE_CONFLICT,
            detail="Field already has a schedule in this time range",
        )
    has_active_rent = rent_repository.field_has_active_rent_in_range(
        db,
        field_id=field_id,
        start_time=start_time,
        end_time=end_time,
        excluded_statuses=excluded_rent_statuses,
        exclude_schedule_id=exclude_schedule_id,
    )

    if has_active_rent:
        raise http_error(
            RENT_ACTIVE_CONFLICT,
            detail="Field already has an active rent in this time range",
        )


def _get_local_tz() -> timezone:
    """Resolve the local timezone for schedule validation.

    Used by: ensure_start_time_in_future.
    """
    try:
        return ZoneInfo(settings.TIMEZONE)
    except ZoneInfoNotFoundError:
        return timezone.utc


__all__ = [
    "get_field",
    "get_user",
    "ensure_start_time_in_future",
    "validate_schedule_window",
    "ensure_field_not_reserved",
]
