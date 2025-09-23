from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, constr


class RegisterRequest(BaseModel):
    name: constr(strip_whitespace=True, min_length=1, max_length=200)
    email: EmailStr
    phone: constr(strip_whitespace=True, min_length=5, max_length=20)
    password: constr(min_length=8, max_length=128)
    rol_id_role: int = Field(..., ge=1)


class LoginRequest(BaseModel):
    email: EmailStr
    password: constr(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id_user: int
    name: str
    email: EmailStr
    phone: str
    status: str
    rol_id_role: int
    created_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
