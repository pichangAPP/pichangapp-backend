from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class ManagerResponse(BaseModel):
    id_user: int
    name: str
    lastname: str
    email: EmailStr
    phone: str
    imageurl: Optional[str] = None
    birthdate: Optional[datetime] = None
    gender: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    status: str
    id_role: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True