from __future__ import annotations

from typing import List, Optional

from datetime import date

from pydantic import BaseModel, ConfigDict

from app.schemas.campus import CampusCreate, CampusResponse


class BusinessBase(BaseModel):
    name: str
    description: str
    ruc: Optional[str] = None
    email_contact: str
    phone_contact: str
    district: str
    address: str
    status: str
    id_membership: int
    imageurl: Optional[str] = None
    min_price: Optional[float] = None


class BusinessCreate(BusinessBase):
    campuses: List[CampusCreate] = []


class BusinessUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    ruc: Optional[str] = None
    email_contact: Optional[str] = None
    phone_contact: Optional[str] = None
    district: Optional[str] = None
    address: Optional[str] = None
    status: Optional[str] = None
    id_membership: Optional[int] = None
    imageurl: Optional[str] = None
    min_price: Optional[float] = None

class BusinessResponse(BusinessBase):
    model_config = ConfigDict(from_attributes=True)

    id_business: int
    campuses: List[CampusResponse]
