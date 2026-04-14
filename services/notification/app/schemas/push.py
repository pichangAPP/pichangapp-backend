"""Esquemas para registro de tokens FCM."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class PushTokenRegister(BaseModel):
    token: str = Field(..., min_length=10)
    platform: Literal["android", "ios"]
    device_name: Optional[str] = Field(None, max_length=200)


class PushTokenDelete(BaseModel):
    token: str = Field(..., min_length=10)


__all__ = ["PushTokenRegister", "PushTokenDelete"]
