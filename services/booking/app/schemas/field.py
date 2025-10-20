from __future__ import annotations

from typing import Optional

from datetime import time

from pydantic import BaseModel, ConfigDict

from app.schemas.sport import SportResponse

class FieldBase(BaseModel):
    field_name: str
    capacity: int
    surface: str
    measurement: str
    price_per_hour: float
    status: str
    open_time: time
    close_time: time
    minutes_wait: float
    id_sport: int


class FieldCreate(FieldBase):
    id_sport: int
    pass


class FieldUpdate(BaseModel):
    field_name: Optional[str] = None
    capacity: Optional[int] = None
    surface: Optional[str] = None
    measurement: Optional[str] = None
    price_per_hour: Optional[float] = None
    status: Optional[str] = None
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    minutes_wait: Optional[float] = None
    id_sport: Optional[int] = None


class FieldResponse(FieldBase):
    model_config = ConfigDict(from_attributes=True)

    id_field: int
    id_campus: int
    sport: SportResponse
