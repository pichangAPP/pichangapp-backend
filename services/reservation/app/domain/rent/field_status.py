"""Field status maintenance for rent workflows."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.integrations import booking_reader
from app.repository import rent_repository

_FIELD_STATUS_ACTIVE = "active"
_FIELD_STATUS_OCCUPIED = "occupied"


def refresh_field_status(
    db: Session,
    field_id: Optional[int],
    *,
    excluded_statuses: Sequence[str],
) -> None:
    """Update the field status based on active rents.

    Used by: RentService after create/update/delete.
    """
    if field_id is None:
        return

    field = booking_reader.get_field_summary(db, field_id)
    if field is None:
        return

    has_pending_rent = rent_repository.field_has_pending_rent(
        db,
        field_id,
        excluded_statuses=list(excluded_statuses),
    )

    target_status = _FIELD_STATUS_OCCUPIED if has_pending_rent else _FIELD_STATUS_ACTIVE

    current_status = (field.status or "").strip().lower()
    if current_status == target_status:
        return

    booking_reader.update_field_status(db, field_id, target_status)


async def reset_field_status_after_time(
    *,
    field_id: Optional[int],
    end_time: Optional[datetime],
    excluded_statuses: Sequence[str],
) -> None:
    """Delay and recompute the field status after a rent ends.

    Used by: RentService background tasks.
    """
    if field_id is None or end_time is None:
        return

    if end_time.tzinfo is None:
        target_end = end_time.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
    else:
        target_end = end_time
        now = datetime.now(target_end.tzinfo)

    delay = (target_end - now).total_seconds()
    if delay > 0:
        await asyncio.sleep(delay)

    db = SessionLocal()
    try:
        refresh_field_status(db, field_id, excluded_statuses=excluded_statuses)
    finally:
        db.close()


__all__ = ["refresh_field_status", "reset_field_status_after_time"]
