from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models import BusinessSocialMedia


def get_business_social_media(
    db: Session, social_media_id: int
) -> Optional[BusinessSocialMedia]:
    return (
        db.query(BusinessSocialMedia)
        .filter(BusinessSocialMedia.id_business_social_media == social_media_id)
        .first()
    )


def get_business_social_media_by_business(
    db: Session, business_id: int
) -> Optional[BusinessSocialMedia]:
    return (
        db.query(BusinessSocialMedia)
        .filter(BusinessSocialMedia.id_business == business_id)
        .first()
    )


def create_business_social_media(
    db: Session, social_media: BusinessSocialMedia
) -> BusinessSocialMedia:
    db.add(social_media)
    db.flush()
    return social_media


def delete_business_social_media(db: Session, social_media: BusinessSocialMedia) -> None:
    db.delete(social_media)
