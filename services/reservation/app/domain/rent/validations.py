"""Validation helpers for rent workflows."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.error_codes import (
    FIELD_NOT_FOUND,
    RENT_SCHEDULE_STARTED,
    SCHEDULE_NOT_FOUND,
    USER_NOT_FOUND,
    http_error,
)
from app.integrations import auth_reader, booking_reader
from app.models.schedule import Schedule
from app.repository import rent_repository, schedule_repository


def get_schedule(db: Session, schedule_id: int) -> Schedule:
    """Fetch a schedule or raise an API error if it does not exist.

    Used by: RentService create/update flows.
    """
    schedule = schedule_repository.get_schedule(db, schedule_id)
    if schedule is None:
        raise http_error(
            SCHEDULE_NOT_FOUND,
            detail="Associated schedule not found",
        )
    return schedule


def ensure_schedule_available(
    db: Session,
    schedule_id: int,
    *,
    excluded_statuses: Sequence[str],
    exclude_rent_id: Optional[int] = None,
) -> None:
    """Validate that a schedule does not have an active rent.

    Used by: RentService before creating/updating rents.
    """
    if rent_repository.schedule_has_active_rent(
        db,
        schedule_id,
        excluded_statuses=list(excluded_statuses),
        exclude_rent_id=exclude_rent_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Schedule already has an active rent",
        )


def ensure_schedule_not_started(schedule: Schedule) -> None:
    """Prevent actions on schedules that already started.

    Used by: RentService before creating rents.
    """
    local_tz = _get_local_tz()
    now_local = datetime.now(local_tz)
    start_time = schedule.start_time
    if start_time is None:
        return
    if start_time.tzinfo is None:
        start_local = start_time.replace(tzinfo=local_tz)
    else:
        start_local = start_time.astimezone(local_tz)

    if start_local <= now_local:
        raise http_error(
            RENT_SCHEDULE_STARTED,
            detail="Schedule has already started",
        )


def ensure_field_exists(db: Session, field_id: int) -> None:
    """Validate that a field exists in booking service.

    Used by: RentService list_by_field.
    """
    field = booking_reader.get_field_summary(db, field_id)
    if field is None:
        raise http_error(
            FIELD_NOT_FOUND,
            detail="Associated field not found",
        )


def ensure_user_exists(db: Session, user_id: int) -> None:
    """Validate that a user exists in auth service.

    Used by: RentService list_by_user/history.
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


def _get_local_tz() -> timezone:
    """Resolve the local timezone for schedule validation.

    Used by: ensure_schedule_not_started.
    """
    try:
        return ZoneInfo(settings.TIMEZONE)
    except ZoneInfoNotFoundError:
        return timezone.utc


__all__ = [
    "get_schedule",
    "ensure_schedule_available",
    "ensure_schedule_not_started",
    "ensure_field_exists",
    "ensure_user_exists",
]
