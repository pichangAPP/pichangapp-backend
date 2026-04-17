from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import WeeklyScheduleClosure
from app.repository import campus_repository, field_repository, weekly_schedule_closure_repository
from app.schemas.weekly_schedule_closure import (
    WeeklyScheduleClosureCreate,
    WeeklyScheduleClosureResponse,
    WeeklyScheduleClosureUpdate,
)


class WeeklyScheduleClosureService:
    def __init__(self, db: Session):
        self.db = db

    def list_for_campus(self, campus_id: int) -> list[WeeklyScheduleClosureResponse]:
        if campus_repository.get_campus(self.db, campus_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campus not found",
            )
        rows = weekly_schedule_closure_repository.list_by_campus(self.db, campus_id)
        return [WeeklyScheduleClosureResponse.model_validate(r) for r in rows]

    def create_for_campus(
        self,
        campus_id: int,
        payload: WeeklyScheduleClosureCreate,
    ) -> WeeklyScheduleClosureResponse:
        if campus_repository.get_campus(self.db, campus_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campus not found",
            )
        field_id = payload.id_field
        if field_id is not None:
            field = field_repository.get_field(self.db, field_id)
            if field is None or field.id_campus != campus_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Field does not belong to this campus",
                )

        data = payload.model_dump()
        data["id_campus"] = campus_id
        row = WeeklyScheduleClosure(**data)
        created = weekly_schedule_closure_repository.create(self.db, row)
        return WeeklyScheduleClosureResponse.model_validate(created)

    def update_closure(
        self,
        closure_id: int,
        payload: WeeklyScheduleClosureUpdate,
    ) -> WeeklyScheduleClosureResponse:
        row = weekly_schedule_closure_repository.get_by_id(self.db, closure_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Weekly schedule closure not found",
            )
        update_data = payload.model_dump(exclude_unset=True)
        new_field_id = update_data.get("id_field", row.id_field)
        if "id_field" in update_data and new_field_id is not None:
            field = field_repository.get_field(self.db, new_field_id)
            if field is None or field.id_campus != row.id_campus:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Field does not belong to this campus",
                )

        for key, value in update_data.items():
            setattr(row, key, value)
        row.updated_at = datetime.now(timezone.utc)
        saved = weekly_schedule_closure_repository.save(self.db, row)
        return WeeklyScheduleClosureResponse.model_validate(saved)

    def delete_closure(self, closure_id: int) -> None:
        row = weekly_schedule_closure_repository.get_by_id(self.db, closure_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Weekly schedule closure not found",
            )
        weekly_schedule_closure_repository.delete(self.db, row)
