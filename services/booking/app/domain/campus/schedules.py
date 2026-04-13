from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from app.integrations import reservation_reader
from app.models import Campus, Field
from app.schemas import CampusScheduleResponse


def populate_available_schedules(db: Session, campuses: Iterable[Campus]) -> None:
    """Agrega el listado de schedules disponibles por campus.

    Usado en: CampusService.list_campuses/get_campus y BusinessService.get/list.
    """
    campus_list = [campus for campus in campuses if campus is not None]
    if not campus_list:
        return

    field_by_id: dict[int, Field] = {}
    for campus in campus_list:
        # Ensure the attribute exists even when there are no fields.
        campus.available_schedules = []  # type: ignore[attr-defined]
        for field in getattr(campus, "fields", []) or []:
            field_by_id[field.id_field] = field

    if not field_by_id:
        return

    now_utc = datetime.now(timezone.utc)

    schedules = reservation_reader.get_available_schedules(
        db,
        field_by_id.keys(),
        start_time=now_utc,
        status="available",
    )

    schedules_by_campus: dict[int, list[CampusScheduleResponse]] = defaultdict(list)

    for schedule in schedules:
        field = field_by_id.get(schedule.id_field)
        if field is None:
            continue

        schedule_response = CampusScheduleResponse(
            id_schedule=schedule.id_schedule,
            id_field=schedule.id_field,
            field_name=field.field_name,
            day_of_week=schedule.day_of_week,
            start_time=schedule.start_time,
            end_time=schedule.end_time,
            price=schedule.price,
            status=schedule.status,
        )
        schedules_by_campus[field.id_campus].append(schedule_response)

    for campus in campus_list:
        campus.available_schedules = schedules_by_campus.get(  # type: ignore[attr-defined]
            campus.id_campus, []
        )
