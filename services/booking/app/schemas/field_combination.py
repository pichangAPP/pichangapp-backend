from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field as PydanticField


class FieldCombinationMemberCreate(BaseModel):
    id_field: int = PydanticField(..., gt=0)
    sort_order: int = 0


class FieldCombinationMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_field: int
    field_name: str
    sort_order: int


class FieldCombinationCreate(BaseModel):
    name: str = PydanticField(..., max_length=200)
    description: Optional[str] = None
    status: str = PydanticField(default="active", max_length=50)
    price_per_hour: Decimal = PydanticField(..., ge=0)
    members: list[FieldCombinationMemberCreate] = PydanticField(..., min_length=2)


class FieldCombinationUpdate(BaseModel):
    name: Optional[str] = PydanticField(None, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = PydanticField(None, max_length=50)
    price_per_hour: Optional[Decimal] = PydanticField(None, ge=0)
    members: Optional[list[FieldCombinationMemberCreate]] = PydanticField(None, min_length=2)


class FieldCombinationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_combination: int
    id_campus: int
    name: str
    description: Optional[str] = None
    status: str
    price_per_hour: Decimal
    created_at: datetime
    updated_at: Optional[datetime] = None
    members: list[FieldCombinationMemberResponse]
