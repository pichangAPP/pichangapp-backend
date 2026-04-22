from __future__ import annotations

from datetime import datetime, time, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.error_codes import WEEKLY_CLOSURE_CONFLICTS_RESERVED_RENT, http_error
from app.core.weekly_schedule_closure_overlap import WeeklyClosureRule
from app.integrations.reservation_reader import find_reserved_rent_id_conflicting_with_weekly_rule
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

    def _field_ids_for_scope(self, campus_id: int, id_field: Optional[int]) -> list[int]:
        if id_field is not None:
            return [int(id_field)]
        fields = field_repository.list_fields_by_campus(self.db, campus_id)
        return [int(f.id_field) for f in fields]

    def _raise_if_rule_conflicts_reserved_rents(
        self,
        *,
        campus_id: int,
        id_field: Optional[int],
        weekday: int,
        local_start_time: Optional[time],
        local_end_time: Optional[time],
        is_active: bool,
    ) -> None:
        if not is_active:
            return
        field_ids = self._field_ids_for_scope(campus_id, id_field)
        rule = WeeklyClosureRule(weekday, local_start_time, local_end_time)
        rid = find_reserved_rent_id_conflicting_with_weekly_rule(
            self.db,
            field_ids=field_ids,
            rule=rule,
        )
        if rid is not None:
            raise http_error(
                WEEKLY_CLOSURE_CONFLICTS_RESERVED_RENT,
                detail=f"id_rent={rid}",
            )

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

        self._raise_if_rule_conflicts_reserved_rents(
            campus_id=campus_id,
            id_field=payload.id_field,
            weekday=payload.weekday,
            local_start_time=payload.local_start_time,
            local_end_time=payload.local_end_time,
            is_active=payload.is_active,
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

        final_active = (
            bool(update_data["is_active"])
            if "is_active" in update_data
            else bool(row.is_active)
        )
        if final_active:
            final_weekday = (
                int(update_data["weekday"]) if "weekday" in update_data else int(row.weekday)
            )
            final_ls = (
                update_data["local_start_time"]
                if "local_start_time" in update_data
                else row.local_start_time
            )
            final_le = (
                update_data["local_end_time"]
                if "local_end_time" in update_data
                else row.local_end_time
            )
            final_field = update_data["id_field"] if "id_field" in update_data else row.id_field
            self._raise_if_rule_conflicts_reserved_rents(
                campus_id=int(row.id_campus),
                id_field=int(final_field) if final_field is not None else None,
                weekday=final_weekday,
                local_start_time=final_ls,
                local_end_time=final_le,
                is_active=True,
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
