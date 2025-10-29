from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field as PydanticField


class CampusScheduleResponse(BaseModel):
    """Represents an available schedule exposed alongside campus data."""

    model_config = ConfigDict(from_attributes=True)

    id_schedule: int
    id_field: int
    field_name: str
    day_of_week: str
    start_time: datetime
    end_time: datetime
    price: Decimal = PydanticField(..., ge=0)
    status: str
