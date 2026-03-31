"""Default value builders for rent data based on schedules."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.integrations import booking_reader
from app.models.rent import Rent
from app.models.schedule import Schedule
from app.schemas.schedule import FieldSummary

_ADMIN_NOTE = "Creado por administrador"


def calculate_minutes(*, start_time, end_time) -> Decimal:
    """Calculate the total minutes between two datetimes.

    Used by: apply_schedule_defaults and rent period calculation.
    """
    duration = end_time - start_time
    if duration.total_seconds() <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Schedule end time must be after start time",
        )

    total_seconds = duration.days * 86400 + duration.seconds
    total_seconds_decimal = Decimal(total_seconds) + (
        Decimal(duration.microseconds) / Decimal(1_000_000)
    )
    minutes = total_seconds_decimal / Decimal(60)
    return minutes.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_period(minutes: Decimal) -> str:
    """Create a human-readable period string for the given duration in minutes.

    Used by: apply_schedule_defaults when period is missing.
    """
    normalized_minutes = minutes.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    hours = int(normalized_minutes // Decimal(60))
    remaining_minutes = (
        normalized_minutes % Decimal(60)
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    segments = []
    if hours:
        segments.append(f"{hours} hour{'s' if hours != 1 else ''}")

    if remaining_minutes:
        remaining_is_int = remaining_minutes == remaining_minutes.to_integral()
        if remaining_is_int:
            minutes_value: str = str(int(remaining_minutes))
        else:
            minutes_value = format(remaining_minutes.normalize(), "f")
        segments.append(
            f"{minutes_value} minute{'s' if remaining_minutes != 1 else ''}"
        )

    if not segments:
        segments.append("0 minutes")

    return " ".join(segments)


def apply_schedule_defaults(
    db: Session,
    *,
    schedule: Schedule,
    rent_data: Dict[str, object],
    schedule_changed: bool,
    existing_rent: Optional[Rent] = None,
    field_summary: Optional[FieldSummary] = None,
) -> None:
    """Populate rent_data with schedule-driven defaults and derived fields.

    Used by: RentService create/update flows.
    """
    rent_data["id_schedule"] = schedule.id_schedule
    rent_data["start_time"] = schedule.start_time
    rent_data["end_time"] = schedule.end_time
    rent_data["mount"] = schedule.price

    minutes = calculate_minutes(
        start_time=schedule.start_time,
        end_time=schedule.end_time,
    )
    rent_data["minutes"] = minutes

    if schedule_changed or existing_rent is None:
        rent_data.setdefault("initialized", schedule.start_time)
        rent_data.setdefault("finished", schedule.end_time)
        rent_data.setdefault("date_log", schedule.start_time)
    else:
        if "initialized" not in rent_data:
            rent_data["initialized"] = existing_rent.initialized
        if "finished" not in rent_data:
            rent_data["finished"] = existing_rent.finished
        if "date_log" not in rent_data:
            rent_data["date_log"] = existing_rent.date_log

    if "capacity" not in rent_data or rent_data["capacity"] is None:
        capacity_source = None
        if field_summary is None and schedule.id_field is not None:
            field_summary = booking_reader.get_field_summary(
                db, schedule.id_field
            )
        if field_summary is not None:
            capacity_source = field_summary.capacity
        elif existing_rent is not None:
            capacity_source = existing_rent.capacity

        if capacity_source is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Unable to determine capacity for rent. Provide the "
                    "capacity explicitly or associate the schedule with a field."
                ),
            )

        rent_data["capacity"] = capacity_source

    if "period" not in rent_data or rent_data["period"] is None:
        if existing_rent is not None and not schedule_changed:
            rent_data["period"] = existing_rent.period
        else:
            rent_data["period"] = format_period(minutes)


def apply_admin_note(notes: Optional[str]) -> str:
    """Ensure the admin note is present when creating admin rents.

    Used by: RentService.create_rent_admin and update_rent_admin.
    """
    if not notes:
        return _ADMIN_NOTE
    if _ADMIN_NOTE.lower() in notes.lower():
        return notes
    return f"{notes}\n{_ADMIN_NOTE}"


def ensure_admin_customer_fields(
    rent_data: Dict[str, object],
    *,
    existing_rent: Optional[Rent] = None,
) -> None:
    """Validate the minimum customer fields for admin-created rents.

    Used by: RentService create/update admin flows.
    """
    required_fields = (
        "customer_full_name",
    )
    missing = []
    for field in required_fields:
        value = rent_data.get(field)
        if value is None and existing_rent is not None:
            value = getattr(existing_rent, field, None)
        if not value:
            missing.append(field)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing admin customer fields: {', '.join(missing)}",
        )


__all__ = [
    "apply_schedule_defaults",
    "apply_admin_note",
    "ensure_admin_customer_fields",
    "calculate_minutes",
    "format_period",
]
