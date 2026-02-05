from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import BusinessSocialMedia
from app.repository import business_repository, business_social_media_repository
from app.schemas import BusinessSocialMediaCreate, BusinessSocialMediaUpdate


class BusinessSocialMediaService:
    def __init__(self, db: Session):
        self.db = db

    def _ensure_business_exists(self, business_id: int) -> None:
        if not business_repository.get_business(self.db, business_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Business {business_id} not found",
            )

    def get_social_media_by_business_id(self, business_id: int) -> BusinessSocialMedia:
        self._ensure_business_exists(business_id)
        social_media = business_social_media_repository.get_business_social_media_by_business(
            self.db, business_id
        )
        if not social_media:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Social media for business {business_id} not found",
            )
        return social_media

    def create_social_media(
        self, business_id: int, social_media_in: BusinessSocialMediaCreate
    ) -> BusinessSocialMedia:
        self._ensure_business_exists(business_id)
        existing = business_social_media_repository.get_business_social_media_by_business(
            self.db, business_id
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update social media",
            ) from exc

    def delete_social_media_by_business_id(self, business_id: int) -> None:
        social_media = self.get_social_media_by_business_id(business_id)
        try:
            business_social_media_repository.delete_business_social_media(self.db, social_media)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete social media",
            ) from exc
