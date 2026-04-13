from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import math
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import settings
from app.integrations import reservation_reader
from app.models import Field


def populate_next_available_time_range(db, fields: list[Field]) -> None:
    """Calcula y asigna el proximo horario disponible por cancha.

    Usado en: FieldService.list_fields y FieldService.get_field.
    """
    field_list = [field for field in fields if field is not None]
    if not field_list:
        return

    field_ids = [field.id_field for field in field_list]
    try:
        local_tz = ZoneInfo(settings.TIMEZONE)
    except ZoneInfoNotFoundError:
        local_tz = timezone.utc

    now_local = datetime.now(local_tz)
    now = now_local.replace(tzinfo=None)
    today = now_local.date()

    schedules = reservation_reader.get_schedules_for_fields_on_date(
        db,
        field_ids,
        target_date=today,
    )

    def _as_naive_local(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        return value.astimezone(local_tz).replace(tzinfo=None)

    def _build_busy_map(
        schedule_items: list[reservation_reader.ScheduleSummary],
    ) -> dict[int, list[tuple[datetime, datetime]]]:
        # Busy map criteria:
        # - Only schedules whose status is NOT "available" are treated as blocking.
        # - This includes any "pending", "hold", "occupied", etc.
        # - Defensive: unknown statuses are considered busy.
        busy: dict[int, list[tuple[datetime, datetime]]] = {}
        for schedule in schedule_items:
            if schedule.status and schedule.status.lower() == "available":
                continue
            start_time = _as_naive_local(schedule.start_time)
            end_time = _as_naive_local(schedule.end_time)
            busy.setdefault(schedule.id_field, []).append((start_time, end_time))
        for schedule_list in busy.values():
            schedule_list.sort(key=lambda item: item[0])
        return busy

    busy_schedules = _build_busy_map(schedules)

    slot_duration = timedelta(hours=1)

    def _format_slot(slot: tuple[datetime, datetime]) -> str:
        return (
            f"{slot[0].strftime('%Y%m%dT%H:%M')} - "
            f"{slot[1].strftime('%Y%m%dT%H:%M')}"
        )

    def _get_open_close(field: Field, target_date: date) -> tuple[datetime, datetime]:
        day_start = datetime.combine(target_date, datetime.min.time())
        open_dt = day_start.replace(
            hour=field.open_time.hour,
            minute=field.open_time.minute,
            second=field.open_time.second,
            microsecond=0,
        )
        close_dt = day_start.replace(
            hour=field.close_time.hour,
            minute=field.close_time.minute,
            second=field.close_time.second,
            microsecond=0,
        )
        return open_dt, close_dt

    def _align_to_slot_boundary(open_dt: datetime, search_start: datetime) -> datetime:
        if search_start <= open_dt:
            return open_dt
        delta_seconds = (search_start - open_dt).total_seconds()
        steps = math.ceil(delta_seconds / slot_duration.total_seconds())
        return open_dt + steps * slot_duration

    def _find_next_available_slot(
        *,
        field: Field,
        target_date: date,
        busy_map: dict[int, list[tuple[datetime, datetime]]],
    ) -> tuple[datetime, datetime] | None:
        field_busy = busy_map.get(field.id_field, [])
        open_dt, close_dt = _get_open_close(field, target_date)
        search_start = max(now, open_dt) if target_date == today else open_dt
        candidate_start = _align_to_slot_boundary(open_dt, search_start)

        while candidate_start + slot_duration <= close_dt:
            candidate_end = candidate_start + slot_duration
            overlap = any(
                busy_start < candidate_end and busy_end > candidate_start
                for busy_start, busy_end in field_busy
            )
            if not overlap:
                return (candidate_start, candidate_end)
            candidate_start += slot_duration

        return None

    pending_next_day: list[Field] = []

    for field in field_list:
        next_available = _find_next_available_slot(
            field=field,
            target_date=today,
            busy_map=busy_schedules,
        )

        if next_available is None:
            pending_next_day.append(field)
            continue

        field.next_available_time_range = _format_slot(  # type: ignore[attr-defined]
            next_available
        )

    if not pending_next_day:
        return

    next_date = today + timedelta(days=1)
    next_day_schedules = reservation_reader.get_schedules_for_fields_on_date(
        db,
        [field.id_field for field in pending_next_day],
        target_date=next_date,
    )
    next_day_busy = _build_busy_map(next_day_schedules)

    for field in pending_next_day:
        next_available = _find_next_available_slot(
            field=field,
            target_date=next_date,
            busy_map=next_day_busy,
        )

        if next_available is None:
            field.next_available_time_range = None  # type: ignore[attr-defined]
            continue

        field.next_available_time_range = _format_slot(  # type: ignore[attr-defined]
            next_available
        )
