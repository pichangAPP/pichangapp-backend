from __future__ import annotations

from fastapi import HTTPException,status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Image
from app.repository import image_repository
from app.schemas import ImageCreate, ImageUpdate
from app.services.campus_service import CampusService


class ImageService:
    def __init__(self, db: Session):
        self.db = db
        self.campus_service = CampusService(db)

    def list_images(self, campus_id: int) -> list[Image]:
        self.campus_service.get_campus(campus_id)
        try:
            return image_repository.list_images_by_campus(self.db, campus_id)
        except SQLAlchemyError as exc:  # pragma: no cover - defensive
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to list images",
            ) from exc

    def get_image(self, image_id: int) -> Image:
        image = image_repository.get_image(self.db, image_id)
        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Image {image_id} not found",
            )
        return image

    def create_image(self, campus_id: int, image_in: ImageCreate) -> Image:
        campus = self.campus_service.get_campus(campus_id)
        image = Image(**image_in.model_dump())
        image.campus = campus
        try:
            image_repository.create_image(self.db, image)
            self.db.commit()
            self.db.refresh(image)
            return image
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create image",
            ) from exc

    def update_image(self, image_id: int, image_in: ImageUpdate) -> Image:
        image = self.get_image(image_id)
        update_data = image_in.model_dump(exclude_unset=True)
        for attr, value in update_data.items():
            setattr(image, attr, value)
        try:
            self.db.flush()
            self.db.commit()
            self.db.refresh(image)
            return image
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update image",
            ) from exc

    def delete_image(self, image_id: int) -> None:
        image = self.get_image(image_id)
        try:
            image_repository.delete_image(self.db, image)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete image",
            ) from exc
