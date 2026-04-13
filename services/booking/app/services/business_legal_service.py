from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.error_codes import (
    BOOKING_CONFLICT,
    BOOKING_INTERNAL_ERROR,
    BUSINESS_NOT_FOUND,
    http_error,
)
from app.domain.business.validations import get_business_or_error
from app.models import BusinessLegal
from app.repository import business_legal_repository
from app.schemas import BusinessLegalCreate, BusinessLegalUpdate


class BusinessLegalService:
    def __init__(self, db: Session):
        self.db = db

    def get_legal_by_business_id(self, business_id: int) -> BusinessLegal:
        get_business_or_error(self.db, business_id)
        legal = business_legal_repository.get_business_legal_by_business(self.db, business_id)
        if not legal:
            raise http_error(
                BUSINESS_NOT_FOUND,
                detail=f"Legal data for business {business_id} not found",
            )
        return legal

    def create_legal(self, business_id: int, legal_in: BusinessLegalCreate) -> BusinessLegal:
        get_business_or_error(self.db, business_id)
        existing = business_legal_repository.get_business_legal_by_business(self.db, business_id)
        if existing:
            raise http_error(
                BOOKING_CONFLICT,
                detail=f"Legal data for business {business_id} already exists",
            )
        legal = BusinessLegal(id_business=business_id, **legal_in.model_dump())
        try:
            business_legal_repository.create_business_legal(self.db, legal)
            self.db.commit()
            self.db.refresh(legal)
            return legal
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise http_error(
                BOOKING_INTERNAL_ERROR,
                detail="Failed to create legal data",
            ) from exc

    def update_legal_by_business_id(
        self, business_id: int, legal_in: BusinessLegalUpdate
    ) -> BusinessLegal:
        legal = self.get_legal_by_business_id(business_id)
        update_data = legal_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(legal, field, value)
        try:
            self.db.flush()
            self.db.commit()
            self.db.refresh(legal)
            return legal
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise http_error(
                BOOKING_INTERNAL_ERROR,
                detail="Failed to update legal data",
            ) from exc

    def delete_legal_by_business_id(self, business_id: int) -> None:
        legal = self.get_legal_by_business_id(business_id)
        try:
            business_legal_repository.delete_business_legal(self.db, legal)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise http_error(
                BOOKING_INTERNAL_ERROR,
                detail="Failed to delete legal data",
            ) from exc
