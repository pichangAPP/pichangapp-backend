from datetime import date, datetime
from typing import List, Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.field import Field
from app.models.schedule import Schedule
from app.models.user import User
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate

from app.repository import schedule_repository


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
        if end_time <= start_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end_time must be after start_time",
            )

        start_time_value = start_time.time()
        end_time_value = end_time.time()

        if start_time_value < field.open_time or end_time_value > field.close_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Schedule must be within the field opening hours"
                    f" ({field.open_time} - {field.close_time})"
                ),
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

    def list_schedules_by_date(
        self,
        *,
        field_id: int,
        target_date: date,
    ) -> List[Schedule]:
        self._get_field(field_id)

        return schedule_repository.list_schedules_by_date(
            self.db,
            field_id=field_id,
            target_date=target_date,
        )
