from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, EmailStr, Field, StringConstraints, constr, field_validator, validator


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
    lastname: NameStr
    email: EmailStr
    phone: PhoneStr
    birthdate: datetime | None = None
    gender: str | None = None
    city: str | None = None
    district: str | None = None
    password: PasswordStr
    id_role: Annotated[int, Field(ge=1)]

class UserUpdateRequest(BaseModel):
    name: NameStr
    lastname: NameStr
    phone: PhoneStr
    imageurl: str | None = None
    birthdate: datetime | None = None
    gender: str | None = None
    city: str | None = None
    district: str | None = None
    status: str
    id_role: int 

    @field_validator("status")
    def validate_status(cls, v: str) -> str:
        allowed = {"active", "disabled"}
        if v not in allowed:
            raise ValueError(f"Status must be one of: {allowed}")
        return v

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    email: EmailStr
    password: PasswordStr


class UserResponse(BaseModel):
    id_user: int
    name: str
    lastname: str
    email: EmailStr
    phone: str
    imageurl: str | None = None
    birthdate: datetime | None = None
    gender: str | None = None
    city: str | None = None
    district: str | None = None
    status: str
    id_role: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


TokenStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class GoogleLoginRequest(BaseModel):
    id_token: TokenStr


class RefreshTokenRequest(BaseModel):
    refresh_token: TokenStr
