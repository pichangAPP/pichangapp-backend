from __future__ import annotations

from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.error_codes import (
    BOOKING_INTERNAL_ERROR,
    FIELD_NOT_FOUND,
    http_error,
)
from app.domain.campus.fields import update_campus_field_count
from app.domain.field.availability import populate_next_available_time_range
from app.domain.field.images import add_images_to_new_field, sync_field_images
from app.domain.field.validations import (
    ensure_field_deletable,
    ensure_sport_exists,
    validate_field_entity,
)
from app.models import Field, Sport
from app.repository import field_repository
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
            populate_next_available_time_range(self.db, fields)
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
        populate_next_available_time_range(self.db, [field])
        return field

    def create_field(self, campus_id: int, field_in: FieldCreate) -> Field:
        campus = self.campus_service.get_campus(campus_id)
        ensure_sport_exists(self.db, field_in.id_sport)
        field_data = field_in.model_dump(exclude={"images"})
        images_data = list(field_in.images or [])
        field = Field(**field_data)
        field.campus = campus
        validate_field_entity(field)
        try:
            field_repository.create_field(self.db, field)
            update_campus_field_count(self.db, campus, delta=1)
            if images_data:
                add_images_to_new_field(field, images_data)
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
            sport = ensure_sport_exists(self.db, update_data["id_sport"])

        for attr, value in update_data.items():
            setattr(field, attr, value)

        if sport is not None:
            field.sport = sport

        if images_data is not None:
            sync_field_images(self.db, field, images_data)

        field.updated_at = datetime.now(timezone.utc)
        validate_field_entity(field)

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

    def delete_field(self, field_id: int) -> None:
        field = self.get_field(field_id)
        today_utc = datetime.now(timezone.utc).date()
        ensure_field_deletable(self.db, field, reference_date=today_utc)

        campus = self.campus_service.get_campus(field.id_campus)

        try:
            update_campus_field_count(self.db, campus, delta=-1)
            field_repository.delete_field(self.db, field)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise http_error(
                BOOKING_INTERNAL_ERROR,
                detail="Failed to delete field",
            ) from exc
