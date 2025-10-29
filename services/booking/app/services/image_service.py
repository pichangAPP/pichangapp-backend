from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Image
from app.repository import field_repository, image_repository
from app.schemas import ImageCreate, ImageUpdate
from app.services.campus_service import CampusService


class ImageService:
    def __init__(self, db: Session):
        self.db = db
        self.campus_service = CampusService(db)

    def list_images(self, campus_id: int) -> list[Image]:
        self.campus_service.get_campus(campus_id)
        try:
            images = image_repository.list_images_by_campus(self.db, campus_id)
            return [image for image in images if image.id_field is None]
        except SQLAlchemyError as exc:  # pragma: no cover - defensive
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to list images",
            ) from exc

    def list_field_images(self, field_id: int) -> list[Image]:
        field = field_repository.get_field(self.db, field_id)
        if not field:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Field {field_id} not found",
            )
        try:
            return image_repository.list_images_by_field(self.db, field_id)
        except SQLAlchemyError as exc:  # pragma: no cover - defensive
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to list field images",
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
        field = None
        if image_in.id_field is not None:
            field = field_repository.get_field(self.db, image_in.id_field)
            if not field:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Field {image_in.id_field} not found",
                )
            if field.id_campus != campus_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Field does not belong to the specified campus",
                )

        if image_in.id_campus is not None and image_in.id_campus != campus_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image campus id does not match the requested campus",
            )

        image = Image(**image_in.model_dump())

        if field is not None:
            image.field = field
            image.campus = field.campus
        else:
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

        campus_provided = "id_campus" in image_in.model_fields_set
        field_provided = "id_field" in image_in.model_fields_set

        new_campus_id = update_data.pop("id_campus", None) if campus_provided else None
        new_field_id = update_data.pop("id_field", None) if field_provided else None

        if campus_provided:
            if new_campus_id is not None:
                campus = self.campus_service.get_campus(new_campus_id)
                image.campus = campus
            else:
                image.campus = None

        if field_provided:
            if new_field_id is not None:
                field = field_repository.get_field(self.db, new_field_id)
                if not field:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Field {new_field_id} not found",
                    )
                if campus_provided and new_campus_id is not None and field.id_campus != new_campus_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Field does not belong to the specified campus",
                    )
                image.field = field
                image.campus = field.campus
            else:
                image.field = None

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