from datetime import datetime
from typing import List, Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy import exists
from sqlalchemy.orm import Session, joinedload

from app.models.field import Field
from app.models.rent import Rent
from app.models.schedule import Schedule
from app.models.user import User
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate


class ScheduleService:

    def __init__(self, db: Session):
        self.db = db

    def _get_field(self, field_id: int) -> Field:
        field = (
            self.db.query(Field)
            .filter(Field.id_field == field_id)
            .first()
        )
        if field is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated field not found",
            )
        return field

    def _get_user(self, user_id: int) -> User:
        user = (
            self.db.query(User)
            .filter(User.id_user == user_id)
            .first()
        )
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

        query = self.db.query(Schedule).options(
            joinedload(Schedule.field),
            joinedload(Schedule.user),
        )

        if field_id is not None:
            query = query.filter(Schedule.id_field == field_id)
        if day_of_week is not None:
            query = query.filter(Schedule.day_of_week == day_of_week)
        if status_filter is not None:
            query = query.filter(Schedule.status == status_filter)

        return query.order_by(Schedule.start_time).all()

    def get_schedule(self, schedule_id: int) -> Schedule:

        schedule = (
            self.db.query(Schedule)
            .options(
                joinedload(Schedule.field),
                joinedload(Schedule.user),
                joinedload(Schedule.rents),
            )
            .filter(Schedule.id_schedule == schedule_id)
            .first()
        )
        if schedule is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schedule not found",
            )
        return schedule

    def create_schedule(self, payload: ScheduleCreate) -> Schedule:

        field = self._get_field(payload.id_field)
        self._get_user(payload.id_user)
        self._validate_schedule_window(
            field=field,
            start_time=payload.start_time,
            end_time=payload.end_time,
        )

        schedule = Schedule(**payload.dict())
        self.db.add(schedule)
        self.db.commit()
        return self.get_schedule(schedule.id_schedule)

    def update_schedule(self, schedule_id: int, payload: ScheduleUpdate) -> Schedule:

        schedule = self.get_schedule(schedule_id)

        update_data = payload.dict(exclude_unset=True)

        field = schedule.field if schedule.field is not None else self._get_field(schedule.id_field)

        if schedule.user is None:
            self._get_user(schedule.id_user)

        if "id_field" in update_data:
            field = self._get_field(update_data["id_field"])
        if "id_user" in update_data:
            self._get_user(update_data["id_user"])

        start_time = update_data.get("start_time", schedule.start_time)
        end_time = update_data.get("end_time", schedule.end_time)

        self._validate_schedule_window(
            field=field,
            start_time=start_time,
            end_time=end_time,
        )

        for attribute, value in update_data.items():
            setattr(schedule, attribute, value)

        self.db.commit()
        return self.get_schedule(schedule_id)

    def delete_schedule(self, schedule_id: int) -> None:

        schedule = self.get_schedule(schedule_id)
        self.db.delete(schedule)
        self.db.commit()

    def list_available_schedules(
        self,
        *,
        field_id: int,
        day_of_week: Optional[str] = None,
        status_filter: Optional[str] = None,
        exclude_rent_statuses: Optional[Sequence[str]] = None,
    ) -> List[Schedule]:

        self._get_field(field_id)

        query = self.db.query(Schedule).options(
            joinedload(Schedule.field),
            joinedload(Schedule.user),
        )

        query = query.filter(Schedule.id_field == field_id)

        if day_of_week is not None:
            query = query.filter(Schedule.day_of_week == day_of_week)
        if status_filter is not None:
            query = query.filter(Schedule.status == status_filter)

        excluded_statuses = [
            status_value
            for status_value in (exclude_rent_statuses or ("cancelled",))
            if status_value
        ]

        active_rent_exists = exists().where(
            Rent.id_schedule == Schedule.id_schedule
        )

        if excluded_statuses:
            active_rent_exists = active_rent_exists.where(
                Rent.status.notin_(excluded_statuses)
            )

        query = query.filter(~active_rent_exists)

        return query.order_by(Schedule.start_time).all()
