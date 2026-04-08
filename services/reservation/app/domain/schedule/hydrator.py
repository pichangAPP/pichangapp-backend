"""Schedule response hydration helpers."""
from __future__ import annotations

from typing import List, Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.error_codes import SCHEDULE_NOT_FOUND, http_error
from app.integrations import auth_reader, booking_reader
from app.models.schedule import Schedule
from app.schemas.schedule import FieldSummary, ScheduleResponse, UserSummary


class ScheduleHydrator:
    """Build schedule responses enriched with field/user data."""

    def __init__(self, db: Session) -> None:
        """Initialize with a DB session for lookups.

        Used by: ScheduleService list/get/create/update.
        """
        self.db = db

    def hydrate_schedule(self, schedule: Optional[Schedule]) -> ScheduleResponse:
        """Hydrate a single schedule into response form.

        Used by: ScheduleService get/create/update.
        """
        if schedule is None:
            raise http_error(
                SCHEDULE_NOT_FOUND,
                detail="Schedule not found",
            )

        field = (
            booking_reader.get_field_summary(self.db, schedule.id_field)
            if schedule.id_field is not None
            else None
        )
        if schedule.id_user is not None:
            try:
                user = auth_reader.get_user_summary(self.db, schedule.id_user)
            except auth_reader.AuthReaderError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=str(exc),
                ) from exc
        else:
            user = None
        return self._build_schedule_response(schedule, field=field, user=user)

    def hydrate_schedules(self, schedules: Sequence[Schedule]) -> List[ScheduleResponse]:
        """Hydrate multiple schedules into response form.

        Used by: ScheduleService list endpoints.
        """
        field_ids = [schedule.id_field for schedule in schedules if schedule.id_field]
        user_ids = [schedule.id_user for schedule in schedules if schedule.id_user]

        fields = booking_reader.get_field_summaries(self.db, field_ids)
        try:
            users = auth_reader.get_user_summaries(self.db, user_ids)
        except auth_reader.AuthReaderError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

        return [
            self._build_schedule_response(
                schedule,
                field=fields.get(schedule.id_field),
                user=users.get(schedule.id_user),
            )
            for schedule in schedules
        ]

    @staticmethod
    def _build_schedule_response(
        schedule: Schedule,
        *,
        field: Optional[FieldSummary],
        user: Optional[UserSummary],
    ) -> ScheduleResponse:
        """Build the final ScheduleResponse object.

        Used by: hydrate_schedule/hydrate_schedules.
        """
        return ScheduleResponse(
            id_schedule=schedule.id_schedule,
            day_of_week=schedule.day_of_week,
            start_time=schedule.start_time,
            end_time=schedule.end_time,
            status=schedule.status,
            id_status=schedule.id_status,
            price=schedule.price,
            id_field=schedule.id_field,
            id_user=schedule.id_user,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
            field=field,
            user=user,
        )


__all__ = ["ScheduleHydrator"]
