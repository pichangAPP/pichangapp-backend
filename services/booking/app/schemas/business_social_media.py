from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class BusinessSocialMediaBase(BaseModel):
    website_url: Optional[str] = None
    instagram_url: Optional[str] = None
    facebook_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    youtube_url: Optional[str] = None
    x_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    whatsapp_url: Optional[str] = None
    google_maps_url: Optional[str] = None

    instagram_handle: Optional[str] = None
    facebook_handle: Optional[str] = None
    tiktok_handle: Optional[str] = None
    youtube_handle: Optional[str] = None
    x_handle: Optional[str] = None
    linkedin_handle: Optional[str] = None

    is_public: bool = True

    @field_validator(
        "website_url",
        "instagram_url",
        "facebook_url",
        "tiktok_url",
        "youtube_url",
        "x_url",
        "linkedin_url",
        "whatsapp_url",
        "google_maps_url",
        "instagram_handle",
        "facebook_handle",
        "tiktok_handle",
        "youtube_handle",
        "x_handle",
        "linkedin_handle",
        mode="before",
    )
    @classmethod
    def _strip_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class BusinessSocialMediaCreate(BusinessSocialMediaBase):
    pass


class BusinessSocialMediaUpdate(BaseModel):
    website_url: Optional[str] = None
    instagram_url: Optional[str] = None
    facebook_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    youtube_url: Optional[str] = None
    x_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    whatsapp_url: Optional[str] = None
    google_maps_url: Optional[str] = None

    instagram_handle: Optional[str] = None
    facebook_handle: Optional[str] = None
    tiktok_handle: Optional[str] = None
    youtube_handle: Optional[str] = None
    x_handle: Optional[str] = None
    linkedin_handle: Optional[str] = None

    is_public: Optional[bool] = None

    @field_validator(
        "website_url",
        "instagram_url",
        "facebook_url",
        "tiktok_url",
        "youtube_url",
        "x_url",
        "linkedin_url",
        "whatsapp_url",
        "google_maps_url",
        "instagram_handle",
        "facebook_handle",
        "tiktok_handle",
        "youtube_handle",
        "x_handle",
        "linkedin_handle",
        mode="before",
    )
    @classmethod
    def _strip_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class BusinessSocialMediaResponse(BusinessSocialMediaBase):
    model_config = ConfigDict(from_attributes=True)

    id_business_social_media: int
    id_business: int
    created_at: datetime
    updated_at: datetime
