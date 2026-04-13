from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class StatusCatalogBase(BaseModel):
    entity: str = Field(..., max_length=20)
    code: str = Field(..., max_length=50)
    name: str = Field(..., max_length=80)
    description: str
    is_final: bool = False
    sort_order: int = 0
    is_active: bool = True


class StatusCatalogCreate(StatusCatalogBase):
    pass


class StatusCatalogUpdate(BaseModel):
    entity: Optional[str] = Field(None, max_length=20)
    code: Optional[str] = Field(None, max_length=50)
    name: Optional[str] = Field(None, max_length=80)
    description: Optional[str] = None
    is_final: Optional[bool] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class StatusCatalogResponse(StatusCatalogBase):
    id_status: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
