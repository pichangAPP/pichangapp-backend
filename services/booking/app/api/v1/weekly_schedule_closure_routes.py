from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.weekly_schedule_closure import (
    WeeklyScheduleClosureCreate,
    WeeklyScheduleClosureResponse,
    WeeklyScheduleClosureUpdate,
)
from app.services.weekly_schedule_closure_service import WeeklyScheduleClosureService

router = APIRouter(tags=["weekly-schedule-closures"])


@router.get(
    "/campuses/{campus_id}/weekly-schedule-closures",
    response_model=list[WeeklyScheduleClosureResponse],
)
def list_weekly_schedule_closures(campus_id: int, db: Session = Depends(get_db)):
    service = WeeklyScheduleClosureService(db)
    return service.list_for_campus(campus_id)


@router.post(
    "/campuses/{campus_id}/weekly-schedule-closures",
    response_model=WeeklyScheduleClosureResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_weekly_schedule_closure(
    campus_id: int,
    payload: WeeklyScheduleClosureCreate,
    db: Session = Depends(get_db),
):
    service = WeeklyScheduleClosureService(db)
    return service.create_for_campus(campus_id, payload)


@router.put(
    "/weekly-schedule-closures/{closure_id}",
    response_model=WeeklyScheduleClosureResponse,
)
def update_weekly_schedule_closure(
    closure_id: int,
    payload: WeeklyScheduleClosureUpdate,
    db: Session = Depends(get_db),
):
    service = WeeklyScheduleClosureService(db)
    return service.update_closure(closure_id, payload)


@router.delete(
    "/weekly-schedule-closures/{closure_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_weekly_schedule_closure(closure_id: int, db: Session = Depends(get_db)):
    service = WeeklyScheduleClosureService(db)
    service.delete_closure(closure_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
