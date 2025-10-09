"""Business logic related to schedules."""

from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.schedule import Schedule
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate


class ScheduleService:
    """Encapsulates schedule related operations."""

    def __init__(self, db: Session):
        self.db = db

    def list_schedules(
        self,
        *,
        field_id: Optional[int] = None,
        day_of_week: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> List[Schedule]:
        """Return schedules optionally filtered by field, day or status."""

        query = self.db.query(Schedule)

        if field_id is not None:
            query = query.filter(Schedule.id_field == field_id)
        if day_of_week is not None:
            query = query.filter(Schedule.day_of_week == day_of_week)
        if status_filter is not None:
            query = query.filter(Schedule.status == status_filter)

        return query.order_by(Schedule.start_time).all()

    def get_schedule(self, schedule_id: int) -> Schedule:
        """Retrieve a schedule by its identifier."""

        schedule = (
            self.db.query(Schedule)
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
        """Create a new schedule instance."""

        schedule = Schedule(**payload.dict())
        self.db.add(schedule)
        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def update_schedule(self, schedule_id: int, payload: ScheduleUpdate) -> Schedule:
        """Update an existing schedule."""

        schedule = self.get_schedule(schedule_id)

        for field, value in payload.dict(exclude_unset=True).items():
            setattr(schedule, field, value)

        self.db.commit()
        self.db.refresh(schedule)
        return schedule

    def delete_schedule(self, schedule_id: int) -> None:
        """Delete a schedule from the database."""

        schedule = self.get_schedule(schedule_id)
        self.db.delete(schedule)
        self.db.commit()
