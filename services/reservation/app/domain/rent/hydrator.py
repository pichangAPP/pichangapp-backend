"""Mapping helpers that hydrate rent models into API responses."""
from __future__ import annotations

from typing import List, Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.error_codes import (
    FIELD_NOT_FOUND,
    RENT_NOT_FOUND,
    SCHEDULE_NOT_FOUND,
    http_error,
)
from app.integrations import auth_reader, booking_reader
from app.models.rent import Rent
from app.models.schedule import Schedule
from app.repository import schedule_repository
from app.schemas.rent import RentResponse, ScheduleSummary
from app.schemas.schedule import FieldSummary, UserSummary


class RentHydrator:
    """Build rent responses enriched with schedule, field, and user data."""

    def __init__(self, db: Session) -> None:
        """Initialize with a DB session for lookups.

        Used by: RentService responses.
        """
        self.db = db

    def hydrate_rent(self, rent: Optional[Rent]) -> RentResponse:
        """Hydrate a single rent into its API response shape.

        Used by: RentService get/create/update flows.
        """
        if rent is None:
            raise http_error(
                RENT_NOT_FOUND,
                detail="Rent not found",
            )
        return self.hydrate_rents([rent])[0]

    def hydrate_rents(self, rents: Sequence[Rent]) -> List[RentResponse]:
        """Hydrate a list of rents into API response shapes.

        Used by: RentService list endpoints.
        """
        schedules: List[Schedule] = []
        for rent in rents:
            schedule = rent.schedule or schedule_repository.get_schedule(
                self.db, rent.id_schedule
            )
            if schedule is None:
                raise http_error(
                    SCHEDULE_NOT_FOUND,
                    detail="Associated schedule not found",
                )
            rent.schedule = schedule
            schedules.append(schedule)

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

        responses: List[RentResponse] = []
        for rent in rents:
            schedule = rent.schedule
            field = fields.get(schedule.id_field)
            user = users.get(schedule.id_user)
            schedule_summary = self._build_schedule_summary(
                schedule,
                field=field,
                user=user,
            )
            responses.append(self._build_rent_response(rent, schedule_summary))
        return responses

    def build_rent_responses_from_rows(self, rows: Sequence[dict]) -> List[RentResponse]:
        """Build rent responses from denormalized query rows.

        Used by: RentService list_rents_by_campus view.
        """
        responses: List[RentResponse] = []
        for row in rows:
            field = FieldSummary(
                id_field=row["field_id_field"],
                field_name=row["field_name"],
                capacity=row["field_capacity"],
                surface=row["field_surface"],
                measurement=row["field_measurement"],
                price_per_hour=row["field_price_per_hour"],
                status=row["field_status"],
                open_time=row["field_open_time"],
                close_time=row["field_close_time"],
                minutes_wait=row["field_minutes_wait"],
                id_sport=row["field_id_sport"],
                id_campus=row["field_id_campus"],
            )
            user = None
            if row["user_id_user"] is not None:
                user = UserSummary(
                    id_user=row["user_id_user"],
                    name=row["user_name"],
                    lastname=row["user_lastname"],
                    email=row["user_email"],
                    phone=row["user_phone"],
                    imageurl=row["user_imageurl"],
                    status=row["user_status"],
                )
            schedule_summary = ScheduleSummary(
                id_schedule=row["id_schedule"],
                day_of_week=row["schedule_day_of_week"],
                start_time=row["schedule_start_time"],
                end_time=row["schedule_end_time"],
                status=row["schedule_status"],
                id_status=row.get("schedule_id_status"),
                price=row["schedule_price"],
                field=field,
                user=user,
            )
            responses.append(
                RentResponse(
                    id_rent=row["id_rent"],
                    period=row["period"],
                    start_time=row["start_time"],
                    end_time=row["end_time"],
                    initialized=row["initialized"],
                    finished=row["finished"],
                    status=row["status"],
                    id_status=row.get("rent_id_status"),
                    minutes=row["minutes"],
                    mount=row["mount"],
                    date_log=row["date_log"],
                    date_create=row["date_create"],
                    payment_deadline=row["payment_deadline"],
                    capacity=row["capacity"],
                    id_payment=row["id_payment"],
                    payment_code=row.get("payment_code"),
                    payment_proof_url=row.get("payment_proof_url"),
                    payment_reviewed_at=row.get("payment_reviewed_at"),
                    payment_reviewed_by=row.get("payment_reviewed_by"),
                    customer_full_name=row.get("customer_full_name"),
                    customer_phone=row.get("customer_phone"),
                    customer_email=row.get("customer_email"),
                    customer_document=row.get("customer_document"),
                    customer_notes=row.get("customer_notes"),
                    id_schedule=row["id_schedule"],
                    schedule=schedule_summary,
                )
            )
        return responses

    @staticmethod
    def _build_schedule_summary(
        schedule: Schedule,
        *,
        field: Optional[FieldSummary],
        user: Optional[UserSummary],
    ) -> ScheduleSummary:
        """Build the nested schedule summary for a rent response.

        Used by: hydrate_rents.
        """
        if field is None:
            raise http_error(
                FIELD_NOT_FOUND,
                detail="Associated field not found",
            )
        return ScheduleSummary(
            id_schedule=schedule.id_schedule,
            day_of_week=schedule.day_of_week,
            start_time=schedule.start_time,
            end_time=schedule.end_time,
            status=schedule.status,
            id_status=schedule.id_status,
            price=schedule.price,
            field=field,
            user=user,
        )

    @staticmethod
    def _build_rent_response(
        rent: Rent,
        schedule: ScheduleSummary,
    ) -> RentResponse:
        """Build the final RentResponse object.

        Used by: hydrate_rents/build_rent_responses_from_rows.
        """
        return RentResponse(
            id_rent=rent.id_rent,
            period=rent.period,
            start_time=rent.start_time,
            end_time=rent.end_time,
            initialized=rent.initialized,
            finished=rent.finished,
            status=rent.status,
            id_status=rent.id_status,
            minutes=rent.minutes,
            mount=rent.mount,
            date_log=rent.date_log,
            date_create=rent.date_create,
            payment_deadline=rent.payment_deadline,
            capacity=rent.capacity,
            id_payment=rent.id_payment,
            payment_code=rent.payment_code,
            payment_proof_url=rent.payment_proof_url,
            payment_reviewed_at=rent.payment_reviewed_at,
            payment_reviewed_by=rent.payment_reviewed_by,
            customer_full_name=rent.customer_full_name,
            customer_phone=rent.customer_phone,
            customer_email=rent.customer_email,
            customer_document=rent.customer_document,
            customer_notes=rent.customer_notes,
            id_schedule=rent.id_schedule,
            schedule=schedule,
        )


__all__ = ["RentHydrator"]
