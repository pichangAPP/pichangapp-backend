from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, EmailStr, Field, StringConstraints


NameStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
PhoneStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=5, max_length=20),
]
PasswordStr = Annotated[str, StringConstraints(min_length=8, max_length=128)]


class RegisterRequest(BaseModel):
    name: NameStr
    email: EmailStr
    phone: PhoneStr
    password: PasswordStr
    id_role: Annotated[int, Field(ge=1)]


class LoginRequest(BaseModel):
    email: EmailStr
    password: PasswordStr


class UserResponse(BaseModel):
    id_user: int
    name: str
    email: EmailStr
    phone: str
    status: str
    id_role: int
    created_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
