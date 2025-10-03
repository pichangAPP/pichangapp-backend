from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Business
from app.repository import business_repository
from app.schemas import BusinessCreate, BusinessUpdate
from app.services.campus_service import build_campus_entity


class BusinessService:
    def __init__(self, db: Session):
        self.db = db

    def list_businesses(self) -> list[Business]:
        try:
            return business_repository.list_businesses(self.db)
        except SQLAlchemyError as exc:  # pragma: no cover - defensive
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to list businesses",
            ) from exc

    def get_business(self, business_id: int) -> Business:
        business = business_repository.get_business(self.db, business_id)
        if not business:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Business {business_id} not found",
            )
        return business

    def create_business(self, business_in: BusinessCreate) -> Business:
        try:
            business = Business(**business_in.model_dump(exclude={"campuses"}))
            for campus_in in business_in.campuses:
                business.campuses.append(build_campus_entity(campus_in))

            business_repository.create_business(self.db, business)
            self.db.commit()
            self.db.refresh(business)
            return business
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create business",
            ) from exc

    def update_business(self, business_id: int, business_in: BusinessUpdate) -> Business:
        business = self.get_business(business_id)
        update_data = business_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(business, field, value)
        try:
            self.db.flush()
            self.db.commit()
            self.db.refresh(business)
            return business
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update business",
            ) from exc

    def delete_business(self, business_id: int) -> None:
        business = self.get_business(business_id)
        try:
            business_repository.delete_business(self.db, business)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete business",
            ) from exc
