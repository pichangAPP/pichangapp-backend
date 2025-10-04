from __future__ import annotations

from fastapi import HTTPException,status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Field
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
            return field_repository.list_fields_by_campus(self.db, campus_id)
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
        return field

    def create_field(self, campus_id: int, field_in: FieldCreate) -> Field:
        campus = self.campus_service.get_campus(campus_id)
        field = Field(**field_in.model_dump())
        field.campus = campus
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
        for attr, value in update_data.items():
            setattr(field, attr, value)
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
