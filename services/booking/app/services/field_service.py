from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import Field, Schedule
from app.repository import field_repository, sport_repository
from app.schemas import FieldCreate, FieldUpdate
from app.services.campus_service import CampusService


class FieldService:
    def __init__(self, db: Session):
        self.db = db
        self.campus_service = CampusService(db)

    def list_fields(self, campus_id: int) -> list[Field]:
        self.campus_service.get_campus(campus_id)
        try:
            fields = field_repository.list_fields_by_campus(self.db, campus_id)
            self._populate_next_available_time_range(fields)
            return fields
        except SQLAlchemyError as exc:  # pragma: no cover - defensive
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to list fields",
            ) from exc

    def get_field(self, field_id: int) -> Field:
        field = field_repository.get_field(self.db, field_id)
        if not field:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Field {field_id} not found",
            )
        self._populate_next_available_time_range([field])
        return field

    def create_field(self, campus_id: int, field_in: FieldCreate) -> Field:
        campus = self.campus_service.get_campus(campus_id)
        self._ensure_sport_exists(field_in.id_sport)
        field = Field(**field_in.model_dump())
        field.campus = campus
        self._validate_field_entity(field)
        try:
            field_repository.create_field(self.db, field)
            self.db.commit()
            self.db.refresh(field)
            return field
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create field",
            ) from exc

    def update_field(self, field_id: int, field_in: FieldUpdate) -> Field:
        field = self.get_field(field_id)
        update_data = field_in.model_dump(exclude_unset=True)

        if "id_sport" in update_data and update_data["id_sport"] is not None:
            self._ensure_sport_exists(update_data["id_sport"])

        for attr, value in update_data.items():
            setattr(field, attr, value)

        self._validate_field_entity(field)

        try:
            self.db.flush()
            self.db.commit()
            self.db.refresh(field)
            return field
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update field",
            ) from exc

    def delete_field(self, field_id: int) -> None:
        field = self.get_field(field_id)
        try:
            field_repository.delete_field(self.db, field)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete field",
            ) from exc

    def _ensure_sport_exists(self, sport_id: int) -> None:
        if sport_repository.get_sport(self.db, sport_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sport {sport_id} not found",
            )

    def _validate_field_entity(self, field: Field) -> None:
        if field.open_time >= field.close_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="open_time must be earlier than close_time",
            )
        if field.capacity <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="capacity must be greater than zero",
            )
        if float(field.price_per_hour) <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="price_per_hour must be greater than zero",
            )
        if float(field.minutes_wait) < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="minutes_wait must be zero or greater",
            )

    def _populate_next_available_time_range(self, fields: list[Field]) -> None:
        field_list = [field for field in fields if field is not None]
        if not field_list:
            return

        field_ids = [field.id_field for field in field_list]
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        schedules = (
            self.db.query(Schedule)
            .filter(Schedule.id_field.in_(field_ids))
            .filter(Schedule.start_time >= now)
            .filter(Schedule.start_time >= start_of_day)
            .filter(Schedule.start_time < end_of_day)
            .filter(func.lower(Schedule.status) == "available")
            .order_by(Schedule.start_time)
            .all()
        )

        next_schedule_by_field: dict[int, Schedule] = {}
        for schedule in schedules:
            if schedule.id_field in next_schedule_by_field:
                continue

            duration = schedule.end_time - schedule.start_time
            if duration != timedelta(hours=1):
                continue

            next_schedule_by_field[schedule.id_field] = schedule

        for field in field_list:
            schedule = next_schedule_by_field.get(field.id_field)
            if schedule is None:
                field.next_available_time_range = None  # type: ignore[attr-defined]
                continue

            formatted = (
                f"{schedule.start_time.strftime('%Y%m%dT%H:%M')} - "
                f"{schedule.end_time.strftime('%Y%m%dT%H:%M')}"
            )
            field.next_available_time_range = formatted  # type: ignore[attr-defined]
