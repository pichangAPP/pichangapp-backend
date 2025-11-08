from __future__ import annotations

from typing import List, Optional

from datetime import time

from pydantic import (
    BaseModel,
    ConfigDict,
    Field as PydanticField,
    field_validator,
    model_validator,
)
from .characteristic import (
    CharacteristicCreate,
    CharacteristicResponse,
    CharacteristicUpdate,
)
from .field import FieldCreate, FieldResponse
from .image import ImageCreate, ImageResponse, ImageUpdate
from .manager import ManagerResponse
from .schedule import CampusScheduleResponse

class CampusBase(BaseModel):
    name: str
    description: str
    address: str
    district: str
    opentime: time
    closetime: time
    status: str
    rating: float = PydanticField(..., ge=0, le=10)
    count_fields: int = PydanticField(..., ge=0)
    coords_x: float = PydanticField(..., ge=-90, le=90)
    coords_y: float = PydanticField(..., ge=-180, le=180)
    id_manager: Optional[int] = None

    @model_validator(mode="after")
    def _validate_schedule(self) -> "CampusBase":
        if self.opentime >= self.closetime:
            raise ValueError("opentime must be earlier than closetime")
        return self


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
    count_fields: Optional[int] = PydanticField(None, ge=0)
    coords_x: Optional[float] = PydanticField(None, ge=-90, le=90)
    coords_y: Optional[float] = PydanticField(None, ge=-180, le=180)
    characteristic: Optional[CharacteristicUpdate] = None
    id_manager: Optional[int] = None
    images: Optional[List[ImageUpdate]] = None

    @model_validator(mode="after")
    def _validate_schedule(self) -> "CampusUpdate":
        if self.opentime is not None and self.closetime is not None:
            if self.opentime >= self.closetime:
                raise ValueError("opentime must be earlier than closetime")
        return self

class CampusResponse(CampusBase):
    model_config = ConfigDict(from_attributes=True)

    id_campus: int
    id_business: int
    id_manager: Optional[int] = None
    characteristic: CharacteristicResponse
    fields: List[FieldResponse]
    images: List[ImageResponse] = PydanticField(default_factory=list)
    manager: Optional[ManagerResponse] = None
    available_schedules: List[CampusScheduleResponse] = PydanticField(default_factory=list)

    @field_validator("images", mode="before")
    @classmethod
    def _only_campus_images(cls, value: list[object]) -> list[object]:
        if isinstance(value, list):
            return [image for image in value if getattr(image, "id_field", None) is None]
        return value

