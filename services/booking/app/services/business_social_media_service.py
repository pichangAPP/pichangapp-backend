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
from app.models import BusinessSocialMedia
from app.repository import business_social_media_repository
from app.schemas import BusinessSocialMediaCreate, BusinessSocialMediaUpdate


class BusinessSocialMediaService:
    def __init__(self, db: Session):
        self.db = db

    def get_social_media_by_business_id(self, business_id: int) -> BusinessSocialMedia:
        get_business_or_error(self.db, business_id)
        social_media = business_social_media_repository.get_business_social_media_by_business(
            self.db, business_id
        )
        if not social_media:
            raise http_error(
                BUSINESS_NOT_FOUND,
                detail=f"Social media for business {business_id} not found",
            )
        return social_media

    def create_social_media(
        self, business_id: int, social_media_in: BusinessSocialMediaCreate
    ) -> BusinessSocialMedia:
        get_business_or_error(self.db, business_id)
        existing = business_social_media_repository.get_business_social_media_by_business(
            self.db, business_id
        )
        if existing:
            raise http_error(
                BOOKING_CONFLICT,
                detail=f"Social media for business {business_id} already exists",
            )
        social_media = BusinessSocialMedia(
            id_business=business_id, **social_media_in.model_dump()
        )
        try:
            business_social_media_repository.create_business_social_media(self.db, social_media)
            self.db.commit()
            self.db.refresh(social_media)
            return social_media
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise http_error(
                BOOKING_INTERNAL_ERROR,
                detail="Failed to create social media",
            ) from exc

    def update_social_media_by_business_id(
        self, business_id: int, social_media_in: BusinessSocialMediaUpdate
    ) -> BusinessSocialMedia:
        social_media = self.get_social_media_by_business_id(business_id)
        update_data = social_media_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(social_media, field, value)
        try:
            self.db.flush()
            self.db.commit()
            self.db.refresh(social_media)
            return social_media
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise http_error(
                BOOKING_INTERNAL_ERROR,
                detail="Failed to update social media",
            ) from exc

    def delete_social_media_by_business_id(self, business_id: int) -> None:
        social_media = self.get_social_media_by_business_id(business_id)
        try:
            business_social_media_repository.delete_business_social_media(self.db, social_media)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise http_error(
                BOOKING_INTERNAL_ERROR,
                detail="Failed to delete social media",
            ) from exc
