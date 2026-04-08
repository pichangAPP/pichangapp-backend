"""Schedule service orchestrating schedule workflows."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List, Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.error_codes import SCHEDULE_NOT_FOUND, http_error
from app.core.status_constants import (
    RENT_FINAL_STATUS_CODES,
    SCHEDULE_EXCLUDED_CONFLICT_STATUS_CODES,
    SCHEDULE_PENDING_STATUS_CODE,
)
from app.domain.schedule.hydrator import ScheduleHydrator
from app.domain.schedule.time_slots import build_time_slots_by_date
from app.domain.schedule.validations import (
    ensure_field_not_reserved,
    ensure_start_time_in_future,
    get_field,
    get_user,
    validate_schedule_window,
)
from app.domain.status_resolver import resolve_status_pair
from app.repository import schedule_repository
from app.schemas.schedule import (
    ScheduleCreate,
    ScheduleResponse,
    ScheduleUpdate,
)

_EXCLUDED_RENT_STATUSES = RENT_FINAL_STATUS_CODES
_CONFLICT_SCHEDULE_EXCLUDED_STATUSES = SCHEDULE_EXCLUDED_CONFLICT_STATUS_CODES


class ScheduleService:
    """Coordinates schedule CRUD and time-slot workflows."""

    def __init__(self, db: Session):
        self.db = db

    def list_schedules(
        self,
        *,
        field_id: Optional[int] = None,
        day_of_week: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> List[ScheduleResponse]:
        hydrator = ScheduleHydrator(self.db)
        schedules = schedule_repository.list_schedules(
            self.db,
            field_id=field_id,
            day_of_week=day_of_week,
            status_filter=status_filter,
        )
        return hydrator.hydrate_schedules(schedules)

    def get_schedule(self, schedule_id: int) -> ScheduleResponse:
        hydrator = ScheduleHydrator(self.db)
        schedule = schedule_repository.get_schedule(self.db, schedule_id)
        if schedule is None:
            raise http_error(
                SCHEDULE_NOT_FOUND,
                detail="Schedule not found",
            )
        return hydrator.hydrate_schedule(schedule)

    def create_schedule(self, payload: ScheduleCreate) -> ScheduleResponse:
        hydrator = ScheduleHydrator(self.db)
        field = get_field(self.db, payload.id_field) if payload.id_field is not None else None

        if payload.id_user is not None:
            get_user(self.db, payload.id_user)

        if field is not None:
            validate_schedule_window(
                field=field,
                start_time=payload.start_time,
                end_time=payload.end_time,
            )
            ensure_field_not_reserved(
                self.db,
                field_id=field.id_field,
                start_time=payload.start_time,
                end_time=payload.end_time,
                exclude_schedule_id=None,
                excluded_schedule_statuses=_CONFLICT_SCHEDULE_EXCLUDED_STATUSES,
                excluded_rent_statuses=_EXCLUDED_RENT_STATUSES,
            )
        ensure_start_time_in_future(payload.start_time)

        if payload.status != SCHEDULE_PENDING_STATUS_CODE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Create schedule only supports status 'pending'",
            )

        schedule_data = payload.model_dump()
        status_code, status_id = resolve_status_pair(
            self.db,
            entity="schedule",
            status_code=SCHEDULE_PENDING_STATUS_CODE,
            status_id=schedule_data.get("id_status"),
        )
        schedule_data["status"] = status_code
        schedule_data["id_status"] = status_id

        schedule = schedule_repository.create_schedule(self.db, schedule_data)
        persisted = schedule_repository.get_schedule(self.db, schedule.id_schedule)
        return hydrator.hydrate_schedule(persisted)

    def update_schedule(self, schedule_id: int, payload: ScheduleUpdate) -> ScheduleResponse:
        hydrator = ScheduleHydrator(self.db)
        schedule = schedule_repository.get_schedule(self.db, schedule_id)
        if schedule is None:
            raise http_error(
                SCHEDULE_NOT_FOUND,
                detail="Schedule not found",
            )

        update_data = payload.model_dump(exclude_unset=True)
        if "status" in update_data or "id_status" in update_data:
            status_code, status_id = resolve_status_pair(
                self.db,
                entity="schedule",
                status_code=update_data.get("status"),
                status_id=update_data.get("id_status"),
            )
            update_data["status"] = status_code
            update_data["id_status"] = status_id

        field = get_field(self.db, schedule.id_field) if schedule.id_field is not None else None
        if schedule.id_user is not None:
            get_user(self.db, schedule.id_user)

        if "id_field" in update_data:
            field_id = update_data["id_field"]
            field = get_field(self.db, field_id) if field_id is not None else None
        if "id_user" in update_data:
            user_id = update_data["id_user"]
            if user_id is not None:
                get_user(self.db, user_id)

        start_time = update_data.get("start_time", schedule.start_time)
        end_time = update_data.get("end_time", schedule.end_time)

        if field is not None:
            validate_schedule_window(
                field=field,
                start_time=start_time,
                end_time=end_time,
            )
            ensure_field_not_reserved(
                self.db,
                field_id=field.id_field,
                start_time=start_time,
                end_time=end_time,
                exclude_schedule_id=schedule_id,
                excluded_schedule_statuses=_CONFLICT_SCHEDULE_EXCLUDED_STATUSES,
                excluded_rent_statuses=_EXCLUDED_RENT_STATUSES,
            )

        for attribute, value in update_data.items():
            setattr(schedule, attribute, value)

        schedule.updated_at = datetime.now(timezone.utc)
        schedule_repository.save_schedule(self.db, schedule)
        persisted = schedule_repository.get_schedule(self.db, schedule_id)
        return hydrator.hydrate_schedule(persisted)

    def delete_schedule(self, schedule_id: int) -> None:
        schedule = schedule_repository.get_schedule(self.db, schedule_id)
        if schedule is None:
            raise http_error(
                SCHEDULE_NOT_FOUND,
                detail="Schedule not found",
            )
        schedule_repository.delete_schedule(self.db, schedule)

    def list_available_schedules(
        self,
        *,
        field_id: int,
        day_of_week: Optional[str] = None,
        status_filter: Optional[str] = None,
        exclude_rent_statuses: Optional[Sequence[str]] = None,
    ) -> List[ScheduleResponse]:
        hydrator = ScheduleHydrator(self.db)
        get_field(self.db, field_id)
        schedules = schedule_repository.list_available_schedules(
            self.db,
            field_id=field_id,
            day_of_week=day_of_week,
            status_filter=status_filter,
            exclude_rent_statuses=exclude_rent_statuses,
        )
        return hydrator.hydrate_schedules(schedules)

    def list_time_slots_by_date(
        self,
        *,
        field_id: int,
        target_date: date,
    ) -> List[dict]:
        field = get_field(self.db, field_id)
        return build_time_slots_by_date(
            self.db,
            field=field,
            target_date=target_date,
        )
