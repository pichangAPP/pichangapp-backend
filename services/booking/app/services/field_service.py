from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import math
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.error_codes import (
    BOOKING_BAD_REQUEST,
    BOOKING_INTERNAL_ERROR,
    BOOKING_NOT_FOUND,
    FIELD_NOT_FOUND,
    http_error,
)
from app.integrations import reservation_reader
from app.core.config import settings
from app.models import Field, Image, Sport
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
            raise http_error(
                BOOKING_INTERNAL_ERROR,
                detail="Failed to list fields",
            ) from exc

    def get_field(self, field_id: int) -> Field:
        field = field_repository.get_field(self.db, field_id)
        if not field:
            raise http_error(
                FIELD_NOT_FOUND,
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
            self._update_campus_field_count(campus, delta=1)
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
            raise http_error(
                BOOKING_INTERNAL_ERROR,
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

        field.updated_at = datetime.now(timezone.utc)
        self._validate_field_entity(field)

        try:
            self.db.flush()
            self.db.commit()
            self.db.refresh(field)
            return field
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise http_error(
                BOOKING_INTERNAL_ERROR,
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
                raise http_error(
                    BOOKING_BAD_REQUEST,
                    detail="Image field id must match the field being updated",
                )

            image_id = image_data.get("id_image")
            if image_id is not None:
                image = existing_images_by_id.get(image_id)
                if image is None:
                    raise http_error(
                        BOOKING_NOT_FOUND,
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
            raise http_error(
                BOOKING_BAD_REQUEST,
                detail="Image field id must match the field being created",
            )
        id_campus = image_data.get("id_campus")
        if id_campus is not None and id_campus != field.id_campus:
            raise http_error(
                BOOKING_BAD_REQUEST,
                detail="Image campus id must match the parent campus",
            )
        image_type = image_data.get("type")
        if image_type != "field":
            raise http_error(
                BOOKING_BAD_REQUEST,
                detail="Field images must have type 'field'",
            )
        return image_data

    def delete_field(self, field_id: int) -> None:
        field = self.get_field(field_id)

        if (field.status or "").lower() == "occupied":
            raise http_error(
                BOOKING_BAD_REQUEST,
                detail="Cannot delete a field while its status is 'occupied'",
            )

        today_utc = datetime.now(timezone.utc).date()
        if field_repository.field_has_upcoming_reservations(
            self.db, field.id_field, reference_date=today_utc
        ):
            raise http_error(
                BOOKING_BAD_REQUEST,
                detail=(
                    "Cannot delete a field with reserved or pending schedules today or later"
                ),
            )

        campus = self.campus_service.get_campus(field.id_campus)

        try:
            self._update_campus_field_count(campus, delta=-1)
            field_repository.delete_field(self.db, field)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise http_error(
                BOOKING_INTERNAL_ERROR,
                detail="Failed to delete field",
            ) from exc

    def _update_campus_field_count(self, campus, *, delta: int) -> None:
        current_value = int(campus.count_fields or 0)
        new_value = current_value + delta
        if new_value < 0:
            new_value = 0
        campus.count_fields = new_value
        campus.updated_at = datetime.now(timezone.utc)
        self.db.flush([campus])


    def _ensure_sport_exists(self, sport_id: int) -> Sport:
        sport = sport_repository.get_sport(self.db, sport_id)
        if sport is None:
            raise http_error(
                BOOKING_NOT_FOUND,
                detail=f"Sport {sport_id} not found",
            )
        return sport

    def _validate_field_entity(self, field: Field) -> None:
        if field.open_time >= field.close_time:
            raise http_error(
                BOOKING_BAD_REQUEST,
                detail="open_time must be earlier than close_time",
            )
        if field.capacity <= 0:
            raise http_error(
                BOOKING_BAD_REQUEST,
                detail="capacity must be greater than zero",
            )
        if float(field.price_per_hour) <= 0:
            raise http_error(
                BOOKING_BAD_REQUEST,
                detail="price_per_hour must be greater than zero",
            )
        if float(field.minutes_wait) < 0:
            raise http_error(
                BOOKING_BAD_REQUEST,
                detail="minutes_wait must be zero or greater",
            )

    def _populate_next_available_time_range(self, fields: list[Field]) -> None:
        field_list = [field for field in fields if field is not None]
        if not field_list:
            return

        field_ids = [field.id_field for field in field_list]
        try:
            local_tz = ZoneInfo(settings.TIMEZONE)
        except ZoneInfoNotFoundError:
            local_tz = timezone.utc

        now_local = datetime.now(local_tz)
        now = now_local.replace(tzinfo=None)
        today = now_local.date()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

        schedules = reservation_reader.get_schedules_for_fields_on_date(
            self.db,
            field_ids,
            target_date=today,
        )

        def _as_naive_local(value: datetime) -> datetime:
            if value.tzinfo is None:
                return value
            return value.astimezone(local_tz).replace(tzinfo=None)

        def _build_busy_map(
            schedule_items: list[reservation_reader.ScheduleSummary],
        ) -> dict[int, list[tuple[datetime, datetime]]]:
            # Busy map criteria:
            # - Only schedules whose status is NOT "available" are treated as blocking.
            # - This includes any "pending", "hold", "occupied", etc.
            # - Defensive: unknown statuses are considered busy.
            busy: dict[int, list[tuple[datetime, datetime]]] = {}
            for schedule in schedule_items:
                if schedule.status and schedule.status.lower() == "available":
                    continue
                start_time = _as_naive_local(schedule.start_time)
                end_time = _as_naive_local(schedule.end_time)
                busy.setdefault(schedule.id_field, []).append((start_time, end_time))
            for schedule_list in busy.values():
                schedule_list.sort(key=lambda item: item[0])
            return busy

        busy_schedules = _build_busy_map(schedules)

        slot_duration = timedelta(hours=1)

        def _format_slot(slot: tuple[datetime, datetime]) -> str:
            return (
                f"{slot[0].strftime('%Y%m%dT%H:%M')} - "
                f"{slot[1].strftime('%Y%m%dT%H:%M')}"
            )

        def _get_open_close(field: Field, target_date: date) -> tuple[datetime, datetime]:
            day_start = datetime.combine(target_date, datetime.min.time())
            open_dt = day_start.replace(
                hour=field.open_time.hour,
                minute=field.open_time.minute,
                second=field.open_time.second,
                microsecond=0,
            )
            close_dt = day_start.replace(
                hour=field.close_time.hour,
                minute=field.close_time.minute,
                second=field.close_time.second,
                microsecond=0,
            )
            return open_dt, close_dt

        def _align_to_slot_boundary(open_dt: datetime, search_start: datetime) -> datetime:
            if search_start <= open_dt:
                return open_dt
            delta_seconds = (search_start - open_dt).total_seconds()
            steps = math.ceil(delta_seconds / slot_duration.total_seconds())
            return open_dt + steps * slot_duration

        def _find_next_available_slot(
            *,
            field: Field,
            target_date: date,
            busy_map: dict[int, list[tuple[datetime, datetime]]],
        ) -> tuple[datetime, datetime] | None:
            field_busy = busy_map.get(field.id_field, [])
            open_dt, close_dt = _get_open_close(field, target_date)
            search_start = max(now, open_dt) if target_date == today else open_dt
            candidate_start = _align_to_slot_boundary(open_dt, search_start)

            while candidate_start + slot_duration <= close_dt:
                candidate_end = candidate_start + slot_duration
                overlap = any(
                    busy_start < candidate_end and busy_end > candidate_start
                    for busy_start, busy_end in field_busy
                )
                if not overlap:
                    return (candidate_start, candidate_end)
                candidate_start += slot_duration

            return None

        pending_next_day: list[Field] = []

        for field in field_list:
            next_available = _find_next_available_slot(
                field=field,
                target_date=today,
                busy_map=busy_schedules,
            )

            if next_available is None:
                pending_next_day.append(field)
                continue

            field.next_available_time_range = _format_slot(  # type: ignore[attr-defined]
                next_available
            )

        if not pending_next_day:
            return

        next_date = today + timedelta(days=1)
        next_day_schedules = reservation_reader.get_schedules_for_fields_on_date(
            self.db,
            [field.id_field for field in pending_next_day],
            target_date=next_date,
        )
        next_day_busy = _build_busy_map(next_day_schedules)

        for field in pending_next_day:
            next_available = _find_next_available_slot(
                field=field,
                target_date=next_date,
                busy_map=next_day_busy,
            )

            if next_available is None:
                field.next_available_time_range = None  # type: ignore[attr-defined]
                continue

            field.next_available_time_range = _format_slot(  # type: ignore[attr-defined]
                next_available
            )
