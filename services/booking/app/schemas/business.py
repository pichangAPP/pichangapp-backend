from __future__ import annotations

from typing import List, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field as PydanticField,
    field_validator,
)

from app.schemas.campus import CampusCreate, CampusResponse


class BusinessBase(BaseModel):
    name: str
    description: str
    ruc: Optional[str] = None
    email_contact: EmailStr
    phone_contact: str
    district: str
    address: str
    status: str
    id_membership: int = PydanticField(..., gt=0)
    imageurl: Optional[str] = None
    min_price: Optional[float] = PydanticField(None, ge=0)

    @field_validator(
        "name",
        "description",
        "phone_contact",
        "district",
        "address",
        "status",
        mode="before",
    )
    @classmethod
    def _strip_and_validate_required(cls, value: str) -> str:
        if value is None:
            raise ValueError("Value must not be null")
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value must not be empty")
        return stripped

    @field_validator("ruc", "imageurl", mode="before")
    @classmethod
    def _strip_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class BusinessCreate(BusinessBase):
    campuses: List[CampusCreate] = PydanticField(default_factory=list)


class BusinessUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    ruc: Optional[str] = None
    email_contact: Optional[EmailStr] = None
    phone_contact: Optional[str] = None
    district: Optional[str] = None
    address: Optional[str] = None
    status: Optional[str] = None
    id_membership: Optional[int] = PydanticField(None, gt=0)
    imageurl: Optional[str] = None
    min_price: Optional[float] = PydanticField(None, ge=0)

    @field_validator(
        "name",
        "description",
        "phone_contact",
        "district",
        "address",
        "status",
        mode="before",
    )
    @classmethod
    def _strip_non_empty(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value must not be empty")
        return stripped

    @field_validator("ruc", "imageurl", mode="before")
    @classmethod
    def _strip_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

class BusinessResponse(BusinessBase):
    model_config = ConfigDict(from_attributes=True)

    id_business: int
    campuses: List[CampusResponse]
