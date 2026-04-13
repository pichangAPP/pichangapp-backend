from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.image_url_validation import validate_https_image_url


class ImageBase(BaseModel):
    name_image: str
    image_url: str
    state: str
    deleted: bool = False
    type: str  # "business", "campus" o "field"
    category: Optional[str] = None  # Ejemplo: "campo", "logo", "estadio"

    @field_validator("image_url")
    @classmethod
    def _validate_image_url(cls, value: str) -> str:
        return validate_https_image_url(value)


class ImageCreate(ImageBase):
    id_campus: Optional[int] = None
    id_business: Optional[int] = None
    id_field: Optional[int] = None


class ImageUpdate(BaseModel):
    id_image: Optional[int] = None
    name_image: Optional[str] = None
    image_url: Optional[str] = None
    state: Optional[str] = None
    deleted: Optional[bool] = None
    type: Optional[str] = None
    category: Optional[str] = None
    id_campus: Optional[int] = None
    id_business: Optional[int] = None
    id_field: Optional[int] = None

    @field_validator("image_url")
    @classmethod
    def _validate_image_url_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return validate_https_image_url(value)


class ImageResponse(ImageBase):
    model_config = ConfigDict(from_attributes=True)

    id_image: int
    id_campus: Optional[int] = None
    id_business: Optional[int] = None
    id_field: Optional[int] = None
    creation_date: datetime
    modification_date: datetime