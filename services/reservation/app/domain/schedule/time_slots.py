"""Time slot generation for schedules."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import List
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.status_constants import (
    RENT_FINAL_STATUS_CODES,
    SCHEDULE_AVAILABLE_STATUS_CODE,
    SCHEDULE_BLOCKING_STATUS_CODES,
    SCHEDULE_EXPIRED_STATUS_CODE,
)
from app.repository import rent_repository, schedule_repository
from app.schemas.schedule import FieldSummary

_EXCLUDED_RENT_STATUSES = RENT_FINAL_STATUS_CODES


def build_time_slots_by_date(
    db: Session,
    *,
    field: FieldSummary,
    target_date: date,
) -> List[dict]:
    """Build 1-hour availability slots for a field on a specific date.

    Used by: ScheduleService.list_time_slots_by_date.
    """
    try:
        local_tz = ZoneInfo(settings.TIMEZONE)
    except ZoneInfoNotFoundError:
        local_tz = timezone.utc

    open_time = datetime.combine(target_date, field.open_time).replace(tzinfo=local_tz)
    close_time = datetime.combine(target_date, field.close_time).replace(tzinfo=local_tz)
    day_start = datetime.combine(target_date, time.min).replace(tzinfo=local_tz)
    day_end = day_start + timedelta(days=1)

    schedules = schedule_repository.list_schedules_by_date(
        db,
        field_id=field.id_field,
        target_date=target_date,
    )

    def _as_naive_local(value: datetime) -> datetime:
        """Convert aware datetimes to naive local time.

        Used by: build_time_slots_by_date internal normalization.
        """
        if value.tzinfo is None:
            return value
        return value.astimezone(local_tz).replace(tzinfo=None)

    open_time = _as_naive_local(open_time)
    close_time = _as_naive_local(close_time)
    day_start = _as_naive_local(day_start)
    day_end = _as_naive_local(day_end)

    # Determinar los segmentos abiertos del día solicitado.
    if close_time > open_time:
        segments = [(open_time, close_time)]
    else:
        # Horario nocturno: se divide en tramo post medianoche y tramo del mismo día.
        segments = [(day_start, close_time), (open_time, day_end)]

    schedule_ids = [
        schedule.id_schedule for schedule in schedules if schedule.id_schedule is not None
    ]

    active_schedule_ids = rent_repository.get_active_schedule_ids(
        db,
        schedule_ids,
        excluded_statuses=_EXCLUDED_RENT_STATUSES,
    )

    # Rangos ocupados en el día (schedules + rents activos).
    # Nota: esto se evalúa con overlaps O(n*m). Para alto volumen se puede
    # ordenar rangos y hacer sweep-line o construir un timeline por slots.
    reserved_ranges = []
    price_by_range = {}
    for schedule in schedules:
        start_time = _as_naive_local(schedule.start_time)
        end_time = _as_naive_local(schedule.end_time)

        if start_time >= end_time:
            continue

        status_value = (schedule.status or "").strip().lower()

        if status_value in SCHEDULE_BLOCKING_STATUS_CODES:
            reserved_ranges.append((start_time, end_time))
        elif status_value and status_value not in (
            SCHEDULE_AVAILABLE_STATUS_CODE,
            SCHEDULE_EXPIRED_STATUS_CODE,
        ):
            reserved_ranges.append((start_time, end_time))
        elif schedule.id_schedule in active_schedule_ids:
            reserved_ranges.append((start_time, end_time))
        else:
            price_value = getattr(schedule, "price", None)
            if price_value is not None:
                price_by_range[(start_time, end_time)] = price_value

    slot_duration = timedelta(hours=1)
    slot_seconds = slot_duration.total_seconds()
    anchor = open_time

    def _next_aligned_start(start: datetime) -> datetime:
        """Alinea el inicio al siguiente múltiplo horario desde el anchor."""
        delta_seconds = (start - anchor).total_seconds()
        remainder = delta_seconds % slot_seconds
        if remainder == 0:
            return start
        return start + timedelta(seconds=(slot_seconds - remainder))

    def _slot_index(start: datetime) -> int:
        """Indice del slot según el anchor y la duración."""
        return int((start - anchor).total_seconds() // slot_seconds)

    today_local = datetime.now(local_tz).date()
    now_value = _as_naive_local(datetime.now(local_tz)) if target_date == today_local else None

    ordered_slots: List[tuple[int, dict]] = []
    slots_by_index: dict[int, dict] = {}

    for segment_start, segment_end in segments:
        # Iteramos por segmentos abiertos del día solicitado (mismo día civil).
        if segment_end <= segment_start:
            continue

        effective_start = segment_start
        if now_value is not None and now_value > effective_start:
            effective_start = now_value

        current_start = _next_aligned_start(effective_start)
        while current_start + slot_duration <= segment_end:
            current_end = current_start + slot_duration
            slot_idx = _slot_index(current_start)
            price_value = price_by_range.get(
                (current_start, current_end), field.price_per_hour
            )
            slot = {
                "start_time": current_start,
                "end_time": current_end,
                "status": SCHEDULE_AVAILABLE_STATUS_CODE,
                "price": price_value,
            }
            ordered_slots.append((slot_idx, slot))
            slots_by_index[slot_idx] = slot

            current_start = current_end

    # Timeline: marcamos slots ocupados en O(n + m) usando índices.
    occupied: set[int] = set()
    for reserved_start, reserved_end in reserved_ranges:
        start_idx = int((reserved_start - anchor).total_seconds() // slot_seconds)
        end_offset = (reserved_end - anchor).total_seconds()
        end_idx = int(end_offset // slot_seconds)
        if end_offset % slot_seconds == 0:
            end_idx -= 1
        if end_idx < start_idx:
            continue
        for idx in range(start_idx, end_idx + 1):
            if idx in slots_by_index:
                occupied.add(idx)

    return [slot for idx, slot in ordered_slots if idx not in occupied]


__all__ = ["build_time_slots_by_date"]
