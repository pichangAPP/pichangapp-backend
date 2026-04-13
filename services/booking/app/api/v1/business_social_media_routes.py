from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas import (
    BusinessSocialMediaCreate,
    BusinessSocialMediaResponse,
    BusinessSocialMediaUpdate,
)
from app.services import BusinessSocialMediaService

router = APIRouter(tags=["business-social-media"])


@router.get(
    "/businesses/{business_id}/social-media",
    response_model=BusinessSocialMediaResponse,
)
def get_media_by_business_id(business_id: int, db: Session = Depends(get_db)):
    service = BusinessSocialMediaService(db)
    return service.get_social_media_by_business_id(business_id)


@router.post(
    "/businesses/{business_id}/social-media",
    response_model=BusinessSocialMediaResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_social_media(
    business_id: int,
    social_media_in: BusinessSocialMediaCreate,
    db: Session = Depends(get_db),
):
    service = BusinessSocialMediaService(db)
    return service.create_social_media(business_id, social_media_in)


@router.put(
    "/businesses/{business_id}/social-media",
    response_model=BusinessSocialMediaResponse,
)
def update_social_media(
    business_id: int,
    social_media_in: BusinessSocialMediaUpdate,
    db: Session = Depends(get_db),
):
    service = BusinessSocialMediaService(db)
    return service.update_social_media_by_business_id(business_id, social_media_in)


@router.delete(
    "/businesses/{business_id}/social-media",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_social_media(business_id: int, db: Session = Depends(get_db)):
    service = BusinessSocialMediaService(db)
    service.delete_social_media_by_business_id(business_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
