"""Weekly admin closure rules (booking.weekly_schedule_closure) vs concrete slots."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional, Protocol, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.error_codes import SCHEDULE_WEEKLY_CLOSURE, http_error
from app.integrations.booking_reader import list_weekly_closure_rules_for_field
from app.models.schedule import Schedule


class _ClosureRuleLike(Protocol):
    weekday: int
    local_start_time: Optional[time]
    local_end_time: Optional[time]


def _local_tz(tz_name: str) -> ZoneInfo | timezone:
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return timezone.utc


def _ensure_aware(value: datetime, tz: ZoneInfo | timezone) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=tz)
    return value


def naive_weekly_closure_block(
    anchor_date: date,
    rule: _ClosureRuleLike,
) -> Optional[tuple[datetime, datetime]]:
    """Naive local [start, end) for a rule anchored on ``anchor_date`` (``anchor_date.weekday()`` must match ``rule.weekday``).

    - Both times ``NULL``: whole local calendar day at anchor.
    - ``end > start``: same-day window.
    - ``end < start`` or ``end == start``: window crosses midnight (``end`` on ``anchor_date + 1``); ``end == start`` means 24h (e.g. 08:00→08:00 next day), aligned with field open/close semantics.
    """
    if anchor_date.weekday() != rule.weekday:
        return None
    if rule.local_start_time is None and rule.local_end_time is None:
        start = datetime.combine(anchor_date, time.min)
        end = datetime.combine(anchor_date + timedelta(days=1), time.min)
        return start, end
    if rule.local_start_time is None or rule.local_end_time is None:
        return None
    s_t = rule.local_start_time
    e_t = rule.local_end_time
    start = datetime.combine(anchor_date, s_t)
    if e_t > s_t:
        end = datetime.combine(anchor_date, e_t)
    else:
        end = datetime.combine(anchor_date + timedelta(days=1), e_t)
    return start, end


def _local_day_chunks(
    start_utc: datetime,
    end_utc: datetime,
    tz: ZoneInfo | timezone,
) -> list[tuple[date, datetime, datetime]]:
    start_a = _ensure_aware(start_utc, tz).astimezone(tz)
    end_a = _ensure_aware(end_utc, tz).astimezone(tz)
    if end_a <= start_a:
        return []

    chunks: list[tuple[date, datetime, datetime]] = []
    cur = start_a
    while cur < end_a:
        day = cur.date()
        if isinstance(tz, ZoneInfo):
            next_mid = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
        else:
            next_mid = datetime.combine(day + timedelta(days=1), time.min).replace(tzinfo=tz)
        seg_end = end_a if end_a <= next_mid else next_mid
        chunks.append((day, cur.replace(tzinfo=None), seg_end.replace(tzinfo=None)))
        cur = seg_end
    return chunks


def utc_interval_overlaps_weekly_closures(
    start_utc: datetime,
    end_utc: datetime,
    rules: Sequence[_ClosureRuleLike],
    *,
    tz_name: str,
) -> bool:
    if not rules:
        return False
    tz = _local_tz(tz_name)
    for day, naive_start, naive_end in _local_day_chunks(start_utc, end_utc, tz):
        for rule in rules:
            for anchor in (day - timedelta(days=1), day):
                blk = naive_weekly_closure_block(anchor, rule)
                if blk is None:
                    continue
                block_start, block_end = blk
                if naive_start < block_end and naive_end > block_start:
                    return True
    return False


def schedule_overlaps_weekly_closure(
    db: Session,
    *,
    field_id: Optional[int],
    start_time: datetime,
    end_time: datetime,
) -> bool:
    if field_id is None:
        return False
    rules = list_weekly_closure_rules_for_field(db, field_id)
    return utc_interval_overlaps_weekly_closures(
        start_time,
        end_time,
        rules,
        tz_name=settings.TIMEZONE,
    )


def raise_if_window_blocked_by_weekly_closure(
    db: Session,
    *,
    field_id: Optional[int],
    start_time: datetime,
    end_time: datetime,
) -> None:
    if schedule_overlaps_weekly_closure(
        db,
        field_id=field_id,
        start_time=start_time,
        end_time=end_time,
    ):
        raise http_error(
            SCHEDULE_WEEKLY_CLOSURE,
            detail="Este horario cae en un cierre recurrente configurado por el administrador.",
        )


def raise_if_schedule_blocked_by_weekly_closure(db: Session, schedule: Schedule) -> None:
    raise_if_window_blocked_by_weekly_closure(
        db,
        field_id=schedule.id_field,
        start_time=schedule.start_time,
        end_time=schedule.end_time,
    )


__all__ = [
    "naive_weekly_closure_block",
    "raise_if_schedule_blocked_by_weekly_closure",
    "raise_if_window_blocked_by_weekly_closure",
    "schedule_overlaps_weekly_closure",
    "utc_interval_overlaps_weekly_closures",
]
