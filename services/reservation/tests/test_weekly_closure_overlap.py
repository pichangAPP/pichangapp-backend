"""Tests for weekly admin closure overlap (local TZ)."""

from __future__ import annotations

from datetime import datetime, time

import pytest
from zoneinfo import ZoneInfo

from app.domain.schedule.weekly_closure import utc_interval_overlaps_weekly_closures
from app.integrations.booking_reader import WeeklyClosureRuleRow


@pytest.fixture
def tz():
    return "America/Lima"


def test_full_day_closure_blocks_same_weekday(tz: str) -> None:
    wed = 2  # Monday=0
    rules = [WeeklyClosureRuleRow(wed, None, None)]
    start = datetime(2026, 4, 15, 10, 0, tzinfo=ZoneInfo(tz))
    end = datetime(2026, 4, 15, 11, 0, tzinfo=ZoneInfo(tz))
    assert start.date().weekday() == wed
    assert utc_interval_overlaps_weekly_closures(start, end, rules, tz_name=tz) is True


def test_full_day_closure_does_not_block_other_weekday(tz: str) -> None:
    wed = 2
    rules = [WeeklyClosureRuleRow(wed, None, None)]
    start = datetime(2026, 4, 16, 10, 0, tzinfo=ZoneInfo(tz))
    end = datetime(2026, 4, 16, 11, 0, tzinfo=ZoneInfo(tz))
    assert start.date().weekday() != wed
    assert utc_interval_overlaps_weekly_closures(start, end, rules, tz_name=tz) is False


def test_partial_window_overlap(tz: str) -> None:
    sat = 5
    rules = [WeeklyClosureRuleRow(sat, time(14, 0), time(17, 0))]
    start = datetime(2026, 4, 18, 15, 0, tzinfo=ZoneInfo(tz))
    end = datetime(2026, 4, 18, 16, 0, tzinfo=ZoneInfo(tz))
    assert start.date().weekday() == sat
    assert utc_interval_overlaps_weekly_closures(start, end, rules, tz_name=tz) is True


def test_partial_window_outside(tz: str) -> None:
    sat = 5
    rules = [WeeklyClosureRuleRow(sat, time(14, 0), time(17, 0))]
    start = datetime(2026, 4, 18, 12, 0, tzinfo=ZoneInfo(tz))
    end = datetime(2026, 4, 18, 13, 0, tzinfo=ZoneInfo(tz))
    assert utc_interval_overlaps_weekly_closures(start, end, rules, tz_name=tz) is False


def test_overnight_closure_covers_next_morning(tz: str) -> None:
    """Wednesday 22:00 → Thursday 06:00 blocks Thursday 05:00 local."""
    wed = 2
    rules = [WeeklyClosureRuleRow(wed, time(22, 0), time(6, 0))]
    start = datetime(2026, 4, 16, 5, 0, tzinfo=ZoneInfo(tz))
    end = datetime(2026, 4, 16, 5, 30, tzinfo=ZoneInfo(tz))
    assert start.weekday() == 3
    assert utc_interval_overlaps_weekly_closures(start, end, rules, tz_name=tz) is True


def test_equal_times_means_24h_block(tz: str) -> None:
    wed = 2
    rules = [WeeklyClosureRuleRow(wed, time(8, 0), time(8, 0))]
    inside = datetime(2026, 4, 15, 20, 0, tzinfo=ZoneInfo(tz)), datetime(2026, 4, 15, 21, 0, tzinfo=ZoneInfo(tz))
    assert utc_interval_overlaps_weekly_closures(inside[0], inside[1], rules, tz_name=tz) is True
    before = datetime(2026, 4, 15, 7, 0, tzinfo=ZoneInfo(tz)), datetime(2026, 4, 15, 7, 30, tzinfo=ZoneInfo(tz))
    assert utc_interval_overlaps_weekly_closures(before[0], before[1], rules, tz_name=tz) is False
