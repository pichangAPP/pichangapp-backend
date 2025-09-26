from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict


class ImageBase(BaseModel):
    name_image: str
    image_url: str
    state: str
    deleted: bool = False


class ImageCreate(ImageBase):
    pass


class ImageUpdate(BaseModel):
    name_image: Optional[str] = None
    image_url: Optional[str] = None
    state: Optional[str] = None
    deleted: Optional[bool] = None


class ImageResponse(ImageBase):
    model_config = ConfigDict(from_attributes=True)

    id_image: int
    id_campus: int
