"""Characterization tests for build_time_slots_by_date (no DB)."""
from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.domain.schedule import time_slots as time_slots_module
from app.domain.schedule.time_slots import build_time_slots_by_date
from app.schemas.schedule import FieldSummary

TZ = ZoneInfo("America/Lima")
# Future date so build_time_slots_by_date does not clip slots with "now"
TARGET_DATE = date(2030, 6, 15)


def _field() -> FieldSummary:
    return FieldSummary(
        id_field=1,
        field_name="Cancha",
        capacity=10,
        surface="grass",
        measurement="30x20",
        price_per_hour=Decimal("100"),
        status="active",
        open_time=time(7, 0),
        close_time=time(22, 0),
        minutes_wait=Decimal("10"),
        id_sport=1,
        id_campus=1,
    )


def _window(h0: int, h1: int) -> tuple[datetime, datetime]:
    return (
        datetime.combine(TARGET_DATE, time(h0, 0), tzinfo=TZ),
        datetime.combine(TARGET_DATE, time(h1, 0), tzinfo=TZ),
    )


class _Sch:
    __slots__ = ("id_schedule", "start_time", "end_time", "status", "price")

    def __init__(
        self,
        sid: int,
        start: datetime,
        end: datetime,
        status: str,
        price: Decimal = Decimal("50"),
    ) -> None:
        self.id_schedule = sid
        self.start_time = start
        self.end_time = end
        self.status = status
        self.price = price


def _slot_hours_naive(slots: list) -> set[int]:
    return {s["start_time"].hour for s in slots}


def test_hold_payment_blocks_hour_slots() -> None:
    st, en = _window(10, 12)
    schedules = [_Sch(1, st, en, "hold_payment")]
    db = MagicMock()

    with (
        patch.object(
            time_slots_module.schedule_repository,
            "list_schedules_by_date",
            return_value=schedules,
        ),
        patch.object(
            time_slots_module.rent_repository,
            "get_active_schedule_ids",
            return_value=set(),
        ),
    ):
        slots = build_time_slots_by_date(db, field=_field(), target_date=TARGET_DATE)

    # 7..21 inclusive = 15 one-hour slots; 10-11 and 11-12 removed
    assert len(slots) == 13
    hours = _slot_hours_naive(slots)
    assert 10 not in hours and 11 not in hours
    assert 7 in hours and 21 in hours


def test_available_without_active_rent_does_not_block() -> None:
    st, en = _window(10, 12)
    schedules = [_Sch(99, st, en, "available")]
    db = MagicMock()

    with (
        patch.object(
            time_slots_module.schedule_repository,
            "list_schedules_by_date",
            return_value=schedules,
        ),
        patch.object(
            time_slots_module.rent_repository,
            "get_active_schedule_ids",
            return_value=set(),
        ),
    ):
        slots = build_time_slots_by_date(db, field=_field(), target_date=TARGET_DATE)

    assert len(slots) == 15
    assert 10 in _slot_hours_naive(slots) and 11 in _slot_hours_naive(slots)


def test_available_with_active_rent_blocks() -> None:
    st, en = _window(10, 12)
    schedules = [_Sch(42, st, en, "available")]
    db = MagicMock()

    with (
        patch.object(
            time_slots_module.schedule_repository,
            "list_schedules_by_date",
            return_value=schedules,
        ),
        patch.object(
            time_slots_module.rent_repository,
            "get_active_schedule_ids",
            return_value={42},
        ),
    ):
        slots = build_time_slots_by_date(db, field=_field(), target_date=TARGET_DATE)

    assert len(slots) == 13
    hours = _slot_hours_naive(slots)
    assert 10 not in hours and 11 not in hours


def test_two_overlapping_available_no_rents_do_not_block() -> None:
    a = _Sch(1, *_window(12, 16), "available", Decimal("85"))
    b = _Sch(2, *_window(13, 15), "available", Decimal("95"))
    db = MagicMock()

    with (
        patch.object(
            time_slots_module.schedule_repository,
            "list_schedules_by_date",
            return_value=[a, b],
        ),
        patch.object(
            time_slots_module.rent_repository,
            "get_active_schedule_ids",
            return_value=set(),
        ),
    ):
        slots = build_time_slots_by_date(db, field=_field(), target_date=TARGET_DATE)

    assert len(slots) == 15
    for h in range(12, 16):
        assert h in _slot_hours_naive(slots)


@pytest.mark.parametrize("status", ("reserved", "fullfilled"))
def test_non_available_non_expired_status_blocks(status: str) -> None:
    st, en = _window(14, 15)
    schedules = [_Sch(3, st, en, status)]
    db = MagicMock()

    with (
        patch.object(
            time_slots_module.schedule_repository,
            "list_schedules_by_date",
            return_value=schedules,
        ),
        patch.object(
            time_slots_module.rent_repository,
            "get_active_schedule_ids",
            return_value=set(),
        ),
    ):
        slots = build_time_slots_by_date(db, field=_field(), target_date=TARGET_DATE)

    assert 14 not in _slot_hours_naive(slots)
    assert len(slots) == 14
