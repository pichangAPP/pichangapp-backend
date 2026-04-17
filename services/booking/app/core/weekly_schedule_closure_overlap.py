"""Detect overlap between concrete UTC intervals and weekly local closure rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class WeeklyClosureRule:
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


def _naive_weekly_closure_block(
    anchor_date: date,
    rule: WeeklyClosureRule,
) -> Optional[tuple[datetime, datetime]]:
    """Same semantics as reservation ``naive_weekly_closure_block`` (overnight / 24h)."""
    if anchor_date.weekday() != rule.weekday:
        return None
    if rule.local_start_time is None and rule.local_end_time is None:
        start = datetime.combine(anchor_date, time.min)
        end = datetime.combine(anchor_date + timedelta(days=1), time.min)
        return start, end
    if rule.local_start_time is None or rule.local_end_time is None:
        return None
    s_t, e_t = rule.local_start_time, rule.local_end_time
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
    """Split [start_utc, end_utc) into per-local-calendar-day naive intervals."""
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
        naive_start = cur.replace(tzinfo=None)
        naive_end = seg_end.replace(tzinfo=None)
        chunks.append((day, naive_start, naive_end))
        cur = seg_end
    return chunks


def utc_interval_overlaps_weekly_closures(
    start_utc: datetime,
    end_utc: datetime,
    rules: Sequence[WeeklyClosureRule],
    *,
    tz_name: str,
) -> bool:
    """Return True when any active rule blocks the whole UTC window."""
    if not rules:
        return False
    tz = _local_tz(tz_name)
    for day, naive_start, naive_end in _local_day_chunks(start_utc, end_utc, tz):
        for rule in rules:
            for anchor in (day - timedelta(days=1), day):
                blk = _naive_weekly_closure_block(anchor, rule)
                if blk is None:
                    continue
                block_start, block_end = blk
                if naive_start < block_end and naive_end > block_start:
                    return True
    return False
