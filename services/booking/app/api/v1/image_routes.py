from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas import ImageCreate, ImageResponse, ImageUpdate
from app.services import ImageService

router = APIRouter(tags=["images"])


@router.get("/campuses/{campus_id}/images", response_model=list[ImageResponse])
def list_images(campus_id: int, db: Session = Depends(get_db)):
    service = ImageService(db)
    return service.list_images(campus_id)


@router.post(
    "/campuses/{campus_id}/images",
    response_model=ImageResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_image(campus_id: int, image_in: ImageCreate, db: Session = Depends(get_db)):
    service = ImageService(db)
    return service.create_image(campus_id, image_in)


@router.get("/fields/{field_id}/images", response_model=list[ImageResponse])
def list_field_images(field_id: int, db: Session = Depends(get_db)):
    service = ImageService(db)
    return service.list_field_images(field_id)


@router.get("/images/{image_id}", response_model=ImageResponse)
def get_image(image_id: int, db: Session = Depends(get_db)):
    service = ImageService(db)
    return service.get_image(image_id)


@router.put("/images/{image_id}", response_model=ImageResponse)
def update_image(image_id: int, image_in: ImageUpdate, db: Session = Depends(get_db)):
    service = ImageService(db)
    return service.update_image(image_id, image_in)


@router.delete("/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_image(image_id: int, db: Session = Depends(get_db)):
    service = ImageService(db)
    service.delete_image(image_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
