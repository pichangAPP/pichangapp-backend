from __future__ import annotations

from typing import List, Optional

from datetime import time

from pydantic import BaseModel, ConfigDict, Field as PydanticField

from app.schemas.characteristic import (
    CharacteristicCreate,
    CharacteristicResponse,
)
from app.schemas.field import FieldCreate, FieldResponse
from app.schemas.image import ImageCreate, ImageResponse


class CampusBase(BaseModel):
    name: str
    description: str
    address: str
    district: str
    opentime: time
    closetime: time
    status: str
    rating: float = PydanticField(..., ge=0, le=10)
    count_fields: int
    coords_x: float
    coords_y: float


class CampusCreate(CampusBase):
    characteristic: CharacteristicCreate
    fields: List[FieldCreate] = []
    images: List[ImageCreate] = []


class CampusUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    district: Optional[str] = None
    opentime: Optional[time] = None
    closetime: Optional[time] = None
    status: Optional[str] = None
    rating: Optional[float] = PydanticField(None, ge=0, le=10)
    count_fields: Optional[int] = None
    coords_x: Optional[float] = None
    coords_y: Optional[float] = None


class CampusResponse(CampusBase):
    model_config = ConfigDict(from_attributes=True)

    id_campus: int
    id_business: int
    characteristic: CharacteristicResponse
    fields: List[FieldResponse]
    images: List[ImageResponse]
