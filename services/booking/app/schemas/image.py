from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ImageBase(BaseModel):
    name_image: str
    image_url: str
    state: str
    deleted: bool = False
    type: str  # "business", "campus" o "field"
    category: Optional[str] = None  # Ejemplo: "campo", "logo", "estadio"


class ImageCreate(ImageBase):
    id_campus: Optional[int] = None
    id_business: Optional[int] = None
    id_field: Optional[int] = None


class ImageUpdate(BaseModel):
    name_image: Optional[str] = None
    image_url: Optional[str] = None
    state: Optional[str] = None
    deleted: Optional[bool] = None
    type: Optional[str] = None
    category: Optional[str] = None
    id_campus: Optional[int] = None
    id_business: Optional[int] = None
    id_field: Optional[int] = None


class ImageResponse(ImageBase):
    model_config = ConfigDict(from_attributes=True)

    id_image: int
    id_campus: Optional[int] = None
    id_business: Optional[int] = None
    id_field: Optional[int] = None
    creation_date: datetime
    modification_date: datetime