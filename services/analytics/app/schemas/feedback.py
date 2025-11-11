from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FeedbackBase(BaseModel):
    rating: Optional[float] = Field(None, ge=0, le=10)
    comment: Optional[str] = Field(None, min_length=1, max_length=1000)


class FeedbackCreate(FeedbackBase):
    id_rent: int = Field(..., ge=1)


class FeedbackResponse(FeedbackBase):
    id_feedback: int
    created_at: datetime
    id_user: int
    id_rent: int

    class Config:
        orm_mode = True


__all__ = ["FeedbackBase", "FeedbackCreate", "FeedbackResponse"]
