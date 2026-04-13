"""Pydantic schema for user data fetched from auth service."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr


class UserSummary(BaseModel):
    id_user: int
    name: str
    lastname: str
    email: EmailStr
    phone: str
    imageurl: Optional[str] = None
    status: str
    id_role: int

    class Config:
        from_attributes = True


__all__ = ["UserSummary"]
