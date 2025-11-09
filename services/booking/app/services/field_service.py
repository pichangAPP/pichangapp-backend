from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import Field, Image, Schedule, Sport
from app.repository import field_repository, image_repository, sport_repository
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
        field_data = field_in.model_dump(exclude={"images"})
        images_data = list(field_in.images or [])
        field = Field(**field_data)
        field.campus = campus
        self._validate_field_entity(field)
        try:
            field_repository.create_field(self.db, field)
            if images_data:
                self._add_images_to_new_field(field, images_data)
            self.db.commit()
            self.db.refresh(field)
            return field
        except HTTPException as exc:
            self.db.rollback()
            raise exc
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create field",
            ) from exc

    def update_field(self, field_id: int, field_in: FieldUpdate) -> Field:
        field = self.get_field(field_id)
        update_data = field_in.model_dump(exclude_unset=True)
        images_data = update_data.pop("images", None)

        sport: Sport | None = None

        if "id_sport" in update_data and update_data["id_sport"] is not None:
            sport = self._ensure_sport_exists(update_data["id_sport"])

        for attr, value in update_data.items():
            setattr(field, attr, value)

        if sport is not None:
            field.sport = sport

        if images_data is not None:
            self._sync_field_images(field, images_data)

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

    def _sync_field_images(
        self, field: Field, images_data: list[dict[str, object]]
    ) -> None:
        existing_images_by_id = {
            image.id_image: image for image in field.images if image.id_image is not None
        }
        incoming_ids: set[int] = set()

        for image_data in images_data:
            id_field = image_data.get("id_field")
            if id_field != field.id_field:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Image field id must match the field being updated",
                )

            image_id = image_data.get("id_image")
            if image_id is not None:
                image = existing_images_by_id.get(image_id)
                if image is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Image {image_id} not found for field {field.id_field}",
                    )
                incoming_ids.add(image_id)
                updated_fields = {
                    key: value
                    for key, value in image_data.items()
                    if key != "id_image"
                }
                for attr, value in updated_fields.items():
                    setattr(image, attr, value)
            else:
                new_image_data = {
                    key: value for key, value in image_data.items() if key != "id_image"
                }
                field.images.append(Image(**new_image_data))

        for image in list(field.images):
            if image.id_image is not None and image.id_image not in incoming_ids:
                field.images.remove(image)
                image_repository.delete_image(self.db, image)

    def _add_images_to_new_field(
        self, field: Field, images_data: list[object]
    ) -> None:
        for image_in in images_data:
            image_payload = (
                image_in.model_dump()
                if hasattr(image_in, "model_dump")
                else dict(image_in)
            )
            validated_payload = self._validate_new_field_image(field, image_payload)
            validated_payload["id_field"] = field.id_field
            validated_payload["id_campus"] = field.id_campus
            field.images.append(Image(**validated_payload))

    def _validate_new_field_image(
        self, field: Field, image_data: dict[str, object]
    ) -> dict[str, object]:
        id_field = image_data.get("id_field")
        if id_field is not None and id_field != field.id_field:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image field id must match the field being created",
            )
        id_campus = image_data.get("id_campus")
        if id_campus is not None and id_campus != field.id_campus:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image campus id must match the parent campus",
            )
        image_type = image_data.get("type")
        if image_type != "field":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Field images must have type 'field'",
            )
        return image_data

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

    def _ensure_sport_exists(self, sport_id: int) -> Sport:
        sport = sport_repository.get_sport(self.db, sport_id)
        if sport is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sport {sport_id} not found",
            )
        return sport

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
        now = datetime.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

        schedules = (
            self.db.query(Schedule)
            .filter(Schedule.id_field.in_(field_ids))
            .filter(func.date(Schedule.start_time) == start_of_day.date())
            .order_by(Schedule.start_time)
            .all()
        )

        def _as_naive(value: datetime) -> datetime:
            return value.replace(tzinfo=None) if value.tzinfo is not None else value

        busy_schedules: dict[int, list[tuple[datetime, datetime]]] = {}
        for schedule in schedules:
            if schedule.status and schedule.status.lower() == "available":
                # Defensive check in case new statuses are introduced later.
                continue
            start_time = _as_naive(schedule.start_time)
            end_time = _as_naive(schedule.end_time)
            busy_schedules.setdefault(schedule.id_field, []).append((start_time, end_time))

        for schedule_list in busy_schedules.values():
            schedule_list.sort(key=lambda item: item[0])

        slot_duration = timedelta(hours=1)

        for field in field_list:
            field_busy = busy_schedules.get(field.id_field, [])

            open_dt = start_of_day.replace(
                hour=field.open_time.hour,
                minute=field.open_time.minute,
                second=field.open_time.second,
                microsecond=0,
            )
            close_dt = start_of_day.replace(
                hour=field.close_time.hour,
                minute=field.close_time.minute,
                second=field.close_time.second,
                microsecond=0,
            )

            search_start = max(now, open_dt)

            # Align the search start to the next slot boundary anchored at open_dt.
            if search_start <= open_dt:
                candidate_start = open_dt
            else:
                delta_seconds = (search_start - open_dt).total_seconds()
                steps = math.ceil(delta_seconds / slot_duration.total_seconds())
                candidate_start = open_dt + steps * slot_duration

            next_available: tuple[datetime, datetime] | None = None

            while candidate_start + slot_duration <= close_dt:
                candidate_end = candidate_start + slot_duration

                overlap = False
                for busy_start, busy_end in field_busy:
                    if busy_start < candidate_end and busy_end > candidate_start:
                        overlap = True
                        break

                if not overlap:
                    next_available = (candidate_start, candidate_end)
                    break

                candidate_start += slot_duration

            if next_available is None:
                field.next_available_time_range = None  # type: ignore[attr-defined]
                continue

            formatted = (
                f"{next_available[0].strftime('%Y%m%dT%H:%M')} - "
                f"{next_available[1].strftime('%Y%m%dT%H:%M')}"
            )
            field.next_available_time_range = formatted  # type: ignore[attr-defined]
