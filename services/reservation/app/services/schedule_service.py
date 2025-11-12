from datetime import date, datetime, timedelta
from typing import List, Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.field import Field
from app.models.schedule import Schedule
from app.models.user import User
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate

from app.repository import rent_repository, schedule_repository

_EXCLUDED_RENT_STATUSES = ("cancelled",)
_CONFLICT_SCHEDULE_EXCLUDED_STATUSES = ("cancelled",)

class ScheduleService:

    def __init__(self, db: Session):
        self.db = db

    def _get_field(self, field_id: int) -> Field:
        field = schedule_repository.get_field(self.db, field_id)
        if field is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated field not found",
            )
        return field
    
    def _get_user(self, user_id: int) -> User:
        user = schedule_repository.get_user(self.db, user_id)

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated user not found",
            )
        return user

    def _validate_schedule_window(
        self, *, field: Field, start_time: datetime, end_time: datetime
    ) -> None:
        # Verifica que el fin sea después del inicio
        if end_time <= start_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end_time must be after start_time",
            )

        # Si el día cambia, no permitir (por defecto)
        if end_time.date() != start_time.date():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Schedules cannot cross over to the next day",
            )

        start_time_value = start_time.time()
        end_time_value = end_time.time()

        # Validar dentro del horario de apertura/cierre
        if start_time_value < field.open_time or end_time_value > field.close_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Schedule must be within the field opening hours"
                    f" ({field.open_time} - {field.close_time})"
                ),
            )


    def _ensure_field_not_reserved(
        self,
        *,
        field_id: int,
        start_time: datetime,
        end_time: datetime,
        exclude_schedule_id: Optional[int] = None,
    ) -> None:
        has_conflicting_schedule = schedule_repository.field_has_schedule_in_range(
            self.db,
            field_id=field_id,
            start_time=start_time,
            end_time=end_time,
            exclude_schedule_id=exclude_schedule_id,
            exclude_statuses=_CONFLICT_SCHEDULE_EXCLUDED_STATUSES,
        )

        if has_conflicting_schedule:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Field already has a schedule in this time range",
            )
        has_active_rent = rent_repository.field_has_active_rent_in_range(
            self.db,
            field_id=field_id,
            start_time=start_time,
            end_time=end_time,
            excluded_statuses=_EXCLUDED_RENT_STATUSES,
            exclude_schedule_id=exclude_schedule_id,
        )

        if has_active_rent:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Field already has an active rent in this time range",
            )

    def list_schedules(
        self,
        *,
        field_id: Optional[int] = None,
        day_of_week: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> List[Schedule]:

        return schedule_repository.list_schedules(
            self.db,
            field_id=field_id,
            day_of_week=day_of_week,
            status_filter=status_filter,
        )

    def get_schedule(self, schedule_id: int) -> Schedule:

        schedule = schedule_repository.get_schedule(self.db, schedule_id)

        if schedule is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schedule not found",
            )
        return schedule

    def create_schedule(self, payload: ScheduleCreate) -> Schedule:

        field: Optional[Field] = None
        if payload.id_field is not None:
            field = self._get_field(payload.id_field)

        if payload.id_user is not None:
            self._get_user(payload.id_user)

        if field is not None:
            self._validate_schedule_window(
                field=field,
                start_time=payload.start_time,
                end_time=payload.end_time
            )
            self._ensure_field_not_reserved(
                field_id=field.id_field,
                start_time=payload.start_time,
                end_time=payload.end_time,
            )

        schedule = schedule_repository.create_schedule(
            self.db, payload.model_dump()
        )
        return schedule_repository.get_schedule(
            self.db, schedule.id_schedule
        )

    def update_schedule(self, schedule_id: int, payload: ScheduleUpdate) -> Schedule:

        schedule = self.get_schedule(schedule_id)

        update_data = payload.model_dump(exclude_unset=True)

        field: Optional[Field] = schedule.field
        if field is None and schedule.id_field is not None:
            field = self._get_field(schedule.id_field)

        if schedule.user is None and schedule.id_user is not None:
            self._get_user(schedule.id_user)

        if "id_field" in update_data:
            field_id = update_data["id_field"]
            field = self._get_field(field_id) if field_id is not None else None
        if "id_user" in update_data:
            user_id = update_data["id_user"]
            if user_id is not None:
                self._get_user(user_id)

        start_time = update_data.get("start_time", schedule.start_time)
        end_time = update_data.get("end_time", schedule.end_time)

        if field is not None:
            self._validate_schedule_window(
                field=field,
                start_time=start_time,
                end_time=end_time,
            )
            self._ensure_field_not_reserved(
                field_id=field.id_field,
                start_time=start_time,
                end_time=end_time,
                exclude_schedule_id=schedule_id,
            )

        for attribute, value in update_data.items():
            setattr(schedule, attribute, value)

        schedule_repository.save_schedule(self.db, schedule)
        return schedule_repository.get_schedule(self.db, schedule_id)

    def delete_schedule(self, schedule_id: int) -> None:

        schedule = self.get_schedule(schedule_id)
        schedule_repository.delete_schedule(self.db, schedule)

    def list_available_schedules(
        self,
        *,
        field_id: int,
        day_of_week: Optional[str] = None,
        status_filter: Optional[str] = None,
        exclude_rent_statuses: Optional[Sequence[str]] = None,
    ) -> List[Schedule]:

        self._get_field(field_id)

        return schedule_repository.list_available_schedules(
            self.db,
            field_id=field_id,
            day_of_week=day_of_week,
            status_filter=status_filter,
            exclude_rent_statuses=exclude_rent_statuses,
        )

    def list_time_slots_by_date(
        self,
        *,
        field_id: int,
        target_date: date,
    ) -> List[dict]:
        field = self._get_field(field_id)

        open_time = datetime.combine(target_date, field.open_time)
        close_time = datetime.combine(target_date, field.close_time)

        if close_time <= open_time:
            close_time += timedelta(days=1)

        schedules = schedule_repository.list_schedules_by_date(
            self.db,
            field_id=field_id,
            target_date=target_date,
        )

        def _as_naive(value: datetime) -> datetime:
            return value.replace(tzinfo=None) if value.tzinfo is not None else value

        open_time = _as_naive(open_time)
        close_time = _as_naive(close_time)

        schedule_ids = [
            schedule.id_schedule for schedule in schedules if schedule.id_schedule is not None
        ]

        active_schedule_ids = rent_repository.get_active_schedule_ids(
            self.db,
            schedule_ids,
            excluded_statuses=_EXCLUDED_RENT_STATUSES,
        )

        reserved_ranges = []
        price_by_range = {}
        for schedule in schedules:
            start_time = _as_naive(schedule.start_time)
            end_time = _as_naive(schedule.end_time)

            if start_time >= end_time:
                continue

            status_value = (schedule.status or "").strip().lower()

            if status_value and status_value != "available":
                reserved_ranges.append((start_time, end_time))
            elif schedule.id_schedule in active_schedule_ids:
                reserved_ranges.append((start_time, end_time))
            else:
                price_value = getattr(schedule, "price", None)
                if price_value is not None:
                    price_by_range[(start_time, end_time)] = price_value

        def _overlaps(slot_start: datetime, slot_end: datetime) -> bool:
            return any(
                slot_start < reserved_end and reserved_start < slot_end
                for reserved_start, reserved_end in reserved_ranges
            )

        slot_duration = timedelta(hours=1)
        slots: List[dict] = []
        current_start = open_time

        while current_start + slot_duration <= close_time:
            current_end = current_start + slot_duration
            if not _overlaps(current_start, current_end):
                price_value = price_by_range.get(
                    (current_start, current_end), field.price_per_hour
                )
                slots.append(
                    {
                        "start_time": current_start,
                        "end_time": current_end,
                        "status": "available",
                        "price": price_value,
                    }
                )

            current_start = current_end

        return slots
