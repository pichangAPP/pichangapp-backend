from __future__ import annotations

from typing import List, Optional

from datetime import time

from pydantic import BaseModel, ConfigDict, Field as PydanticField

from .characteristic import (
    CharacteristicCreate,
    CharacteristicResponse,
    CharacteristicUpdate,
)
from .field import FieldCreate, FieldResponse
from .image import ImageCreate, ImageResponse
from .manager import ManagerResponse

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
    characteristic: Optional[CharacteristicUpdate] = None


class CampusResponse(CampusBase):
    model_config = ConfigDict(from_attributes=True)

    id_campus: int
    id_business: int
    id_manager: Optional[int] = None
    characteristic: CharacteristicResponse
    fields: List[FieldResponse]
    images: List[ImageResponse]
    manager: Optional[ManagerResponse] = None

