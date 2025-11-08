from __future__ import annotations

from typing import Optional

from datetime import time

from pydantic import (
    BaseModel,
    ConfigDict,
    Field as PydanticField,
    model_validator,
)

from app.schemas.image import ImageCreate, ImageResponse, ImageUpdate
from app.schemas.sport import SportResponse

class FieldBase(BaseModel):
    field_name: str
    capacity: int = PydanticField(..., gt=0)
    surface: str
    measurement: str
    price_per_hour: float = PydanticField(..., gt=0)
    status: str
    open_time: time
    close_time: time
    minutes_wait: float = PydanticField(..., ge=0)

    @model_validator(mode="after")
    def _validate_schedule(self) -> "FieldBase":
        if self.open_time >= self.close_time:
            raise ValueError("open_time must be earlier than close_time")
        return self
    

class FieldCreate(FieldBase):
    id_sport: int = PydanticField(..., gt=0)
    images: list[ImageCreate] = []


class FieldUpdate(BaseModel):
    field_name: Optional[str] = None
    capacity: Optional[int] = PydanticField(None, gt=0)
    surface: Optional[str] = None
    measurement: Optional[str] = None
    price_per_hour: Optional[float] = PydanticField(None, gt=0)
    status: Optional[str] = None
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    minutes_wait: Optional[float] = PydanticField(None, ge=0)
    id_sport: Optional[int] = PydanticField(None, gt=0)
    images: Optional[list[ImageUpdate]] = None

    @model_validator(mode="after")
    def _validate_schedule(self) -> "FieldUpdate":
        if self.open_time is not None and self.close_time is not None:
            if self.open_time >= self.close_time:
                raise ValueError("open_time must be earlier than close_time")
        return self


class FieldResponse(FieldBase):
    model_config = ConfigDict(from_attributes=True)

    id_field: int
    id_campus: int
    sport: SportResponse
    images: list[ImageResponse] = PydanticField(default_factory=list)
    next_available_time_range: Optional[str] = None

