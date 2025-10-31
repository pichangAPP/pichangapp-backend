"""API routes for managing schedules."""

from datetime import date
from typing import List, Optional, Sequence

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.schedule import (
    ScheduleCreate,
    ScheduleResponse,
    ScheduleTimeSlotResponse,
    ScheduleUpdate,
)
from app.services.schedule_service import ScheduleService

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.get("/", response_model=List[ScheduleResponse])
def list_schedules(
    *,
    db: Session = Depends(get_db),
    field_id: Optional[int] = Query(None, description="Filter by field identifier"),
    day_of_week: Optional[str] = Query(None, description="Filter by day of week"),
    status: Optional[str] = Query(None, description="Filter by schedule status"),
) -> List[ScheduleResponse]:
    """Retrieve all schedules optionally filtered by field, day or status."""

    service = ScheduleService(db)
    schedules = service.list_schedules(
        field_id=field_id,
        day_of_week=day_of_week,
        status_filter=status,
    )
    return schedules


@router.get("/time-slots", response_model=List[ScheduleTimeSlotResponse])
def list_schedule_time_slots(
    *,
    db: Session = Depends(get_db),
    field_id: int = Query(..., description="Field identifier"),
    date_value: Optional[date] = Query(
        None,
        alias="date",
        description=(
            "Date to filter schedules in ISO format (YYYY-MM-DD). Defaults to the current "
            "date. Example: /schedules/time-slots?field_id=1&date=2024-05-15"
        ),
        example="2024-05-15",
    ),
) -> List[ScheduleTimeSlotResponse]:
    """Retrieve one-hour time slots within the field schedule for the selected date."""

    service = ScheduleService(db)
    target_date = date_value or date.today()
    schedules = service.list_time_slots_by_date(
        field_id=field_id,
        target_date=target_date,
    )
    return schedules

@router.get("/available", response_model=List[ScheduleResponse])
def list_available_schedules(
    *,
    db: Session = Depends(get_db),
    field_id: int = Query(..., description="Field identifier"),
    day_of_week: Optional[str] = Query(None, description="Filter by day of week"),
    status: Optional[str] = Query(
        None,
        description="Filter by schedule status before availability rules",
    ),
    exclude_rent_statuses: Optional[Sequence[str]] = Query(
        ("cancelled",),
        description=(
            "Rent statuses that should not block the schedule availability. "
            "Provide multiple values to exclude additional statuses."
        ),
    ),
) -> List[ScheduleResponse]:
    """Retrieve available schedules for a field applying rent-based constraints."""

    service = ScheduleService(db)
    schedules = service.list_available_schedules(
        field_id=field_id,
        day_of_week=day_of_week,
        status_filter=status,
        exclude_rent_statuses=exclude_rent_statuses,
    )
    return schedules


@router.get("/{schedule_id}", response_model=ScheduleResponse)
def get_schedule(schedule_id: int, db: Session = Depends(get_db)) -> ScheduleResponse:
    """Retrieve a schedule by its identifier."""

    service = ScheduleService(db)
    return service.get_schedule(schedule_id)


@router.post("/", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(
    payload: ScheduleCreate,
    db: Session = Depends(get_db),
) -> ScheduleResponse:
    """Create a new schedule."""

    service = ScheduleService(db)
    return service.create_schedule(payload)


@router.put("/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    db: Session = Depends(get_db),
) -> ScheduleResponse:
    """Update a schedule."""

    service = ScheduleService(db)
    return service.update_schedule(schedule_id, payload)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a schedule."""

    service = ScheduleService(db)
    service.delete_schedule(schedule_id)
