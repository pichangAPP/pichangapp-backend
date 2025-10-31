from datetime import datetime, time
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator, ValidationInfo


class ScheduleBase(BaseModel):
    day_of_week: str = Field(..., max_length=30)
    start_time: datetime
    end_time: datetime
    status: str = Field(..., max_length=30)
    price: Decimal = Field(..., ge=0)
    id_field: int = Field(..., gt=0)
    id_user: int = Field(..., gt=0)

    @field_validator("end_time")
    def validate_time_range(cls, end_time: datetime, info: ValidationInfo) -> datetime:
        start_time = info.data.get("start_time")
        if start_time and end_time <= start_time:
            raise ValueError("end_time must be after start_time")
        return end_time

class ScheduleCreate(ScheduleBase):
    pass


class ScheduleUpdate(BaseModel):
    day_of_week: Optional[str] = Field(None, max_length=30)
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    status: Optional[str] = Field(None, max_length=30)
    price: Optional[Decimal] = Field(None, ge=0)
    id_field: Optional[int] = Field(None, gt=0)
    id_user: Optional[int] = Field(None, gt=0)

    @field_validator("end_time")
    def validate_time_range(cls, end_time: Optional[datetime], info: ValidationInfo) -> Optional[datetime]:
        start_time = info.data.get("start_time")
        if end_time is not None and start_time is not None and end_time <= start_time:
            raise ValueError("end_time must be after start_time")
        return end_time


class FieldSummary(BaseModel):
    id_field: int
    field_name: str
    capacity: int
    surface: str
    measurement: str
    price_per_hour: Decimal
    status: str
    open_time: time
    close_time: time
    minutes_wait: Decimal
    id_sport: int
    id_campus: int

    class Config:
        orm_mode = True


class UserSummary(BaseModel):
    id_user: int
    name: str
    lastname: str
    email: str
    phone: str
    imageurl: Optional[str]
    status: str

    class Config:
        orm_mode = True


class ScheduleResponse(ScheduleBase):
    id_schedule: int
    field: FieldSummary
    user: UserSummary

    class Config:
        orm_mode = True


class ScheduleTimeSlotResponse(BaseModel):
    start_time: datetime
    end_time: datetime
    status: str

    class Config:
        orm_mode = True
